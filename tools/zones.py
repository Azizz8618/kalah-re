#!/usr/bin/env python3
"""zones.py — чтение и запись зон в образах томов БЭСМ-6 (7,25 МБ и 29 МБ).

Геометрия: зона = 8 служебных слов (64 байта) + 1024 слова данных (8192 байта),
шаг 8256 байт; слово — 48 разрядов, хранится 8 байтами little-endian.

Два формата служебных слов зоны:
  7m  (ЕС-5052, 7,25 МБ, 0o1767 зон):    ID дорожки = 2*зона (w0), 2*зона+1 (w4)
  29m (ЕС-5061, 29 МБ, 6144(8) зон):     ID дорожки = зона   (w0), зона+1   (w4)
КС зоны — сквозная (end-around) сумма 1024 слов данных в 48 разрядов,
хранится в w3 и w7 (сверено с эталонным MD/EC5061/2061: 35/35 зон).

ПУЛЬТ адресует зоны со сдвигом +4: команда «зонгп 51 1044» кладёт группу в
физические зоны 0o1050..; сдвиг применяется по умолчанию (--raw-zone его снимает).

Примеры:
  zones.py info  MD/2061
  zones.py verify MD/2061 --zone 1044 --zones 6
  zones.py read  MD/2061 --zone 1044 --zones 6 --to-file group.bin
  zones.py write MD/2061 --zone 1044 --from-image ~/.besm6/1234 --from-zone 128
  zones.py write MD/2061 --zone 1044 --from-file game.bin
  zones.py selftest

Запись делает резервную копию образа рядом: <image>.bak-zones.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys

ZONE = 8256
DATA = 8192
NDATA = 1024
WORD48 = (1 << 48) - 1
PULT_OFFSET = 4           # «зонгп N» пишет в физическую зону N+4

CAPACITY = {              # полная ёмкость дисковода, зон
    '7m':  0o1767,        # ЕС-5052, 7,25 МБ
    '29m': 0o6144,        # ЕС-5061, 29 МБ
}


def checksum(words) -> int:
    s = sum(words)
    while s >> 48:
        s = (s & WORD48) + (s >> 48)
    return s & WORD48


def zone_count(path: int) -> int:
    return os.path.getsize(path) // ZONE


def detect_format(path) -> str:
    return '29m' if zone_count(path) >= 0o3000 else '7m'


def volume_number(path: str) -> int:
    digits = ''.join(c for c in os.path.basename(path) if c.isdigit())
    return int(digits[-4:]) if len(digits) >= 4 else 0


def magic_word(volume: int) -> int:
    return (0o1370707 << 24) | ((volume & 0xFFF) << 12)


def zone_arg(s: str) -> int:
    """Номер зоны: без префикса — ВОСЬМЕРИЧНЫЙ (как принято в ПУЛЬТ/ДИСПАК),
    с префиксом 0x/0o/0b — как записано."""
    s = s.strip()
    return int(s, 0) if s[:2].lower() in ('0x', '0o', '0b') else int(s, 8)


def pult_to_phys(zone: int, raw: bool) -> int:
    return zone if raw else zone + PULT_OFFSET


def phys_to_pult(zone: int, raw: bool) -> int:
    return zone if raw else zone - PULT_OFFSET


def words_of(data: bytes):
    return [int.from_bytes(data[8 * j:8 * j + 8], 'little') & WORD48
            for j in range(len(data) // 8)]


def zone_header(image: bytearray, zone: int) -> bytearray:
    return bytearray(image[zone * ZONE:zone * ZONE + 64])


def set_track(hdr: bytearray, word_index: int, track: int) -> None:
    off = word_index * 8
    v = int.from_bytes(hdr[off:off + 8], 'little')
    v &= ~(((1 << 12) - 1) << 36)
    v |= (track & 0xFFF) << 36
    hdr[off:off + 8] = v.to_bytes(8, 'little')


def build_header(base: bytearray, zone: int, fmt: str, data: bytes) -> bytearray:
    hdr = bytearray(base)
    t0 = 2 * zone if fmt == '7m' else zone
    set_track(hdr, 0, t0)
    set_track(hdr, 4, t0 + 1)
    ks = checksum(words_of(data))
    for wi in (3, 7):
        hdr[wi * 8:wi * 8 + 8] = ks.to_bytes(8, 'little')
    return hdr


def read_zone_data(image: bytes, zone: int) -> bytes:
    return image[zone * ZONE + 64:(zone + 1) * ZONE]


def cmd_info(args) -> int:
    fmt = args.format or detect_format(args.image)
    print(f"{args.image}: {zone_count(args.image)} зон (0o{zone_count(args.image):o}), "
          f"формат {fmt}")


def cmd_verify(args) -> int:
    image = open(args.image, 'rb').read()
    fmt = args.format or detect_format(args.image)
    ok = True
    for k in range(args.zones):
        pz = pult_to_phys(args.zone + k, args.raw_zone)
        hdr = words_of(image[pz * ZONE:pz * ZONE + 64])
        data = image[pz * ZONE + 64:(pz + 1) * ZONE]
        ks = checksum(words_of(data))
        want = (2 * pz if fmt == '7m' else pz)
        good = ks == hdr[3] == hdr[7] and (hdr[0] >> 36) == want
        ok &= good
        print(f"  ПУЛЬТ-зона {args.zone + k} (физ. 0o{pz:o}): "
              f"дорожка={hdr[0] >> 36} (ждали {want}) КС={ks:012x} "
              f"{'ок' if good else 'ОШИБКА'}")
    return 0 if ok else 1


def cmd_read(args) -> int:
    image = open(args.image, 'rb').read()
    with open(args.to_file, 'wb') as out:
        for k in range(args.zones):
            pz = pult_to_phys(args.zone + k, args.raw_zone)
            out.write(read_zone_data(image, pz))
    print(f"{args.to_file}: выгружено {args.zones} зон(ы) данных с 0o"
          f"{pult_to_phys(args.zone, args.raw_zone):o}")
    return 0


def _write_payloads(path, pult_zone, fmt, raw_zone, payloads) -> None:
    shutil.copyfile(path, path + '.bak-zones')
    image = bytearray(open(path, 'rb').read())
    nzones = len(image) // ZONE
    for k, payload in enumerate(payloads):
        pz = pult_to_phys(pult_zone + k, raw_zone)
        if pz >= nzones:
            sys.exit(f"зона 0o{pz:o} вне образа (всего {nzones})")
        payload = payload.ljust(DATA, b'\x00')[:DATA]
        hdr = build_header(zone_header(image, pz), pz, fmt, payload)
        image[pz * ZONE:pz * ZONE + 64] = hdr
        image[pz * ZONE + 64:(pz + 1) * ZONE] = payload
    open(path, 'wb').write(image)
    print(f"{path}: записано {len(payloads)} зон(ы) с ПУЛЬТ-зоны {pult_zone} "
          f"(формат {fmt}); резерв: {path}.bak-zones")


def cmd_write(args) -> int:
    fmt = args.format or detect_format(args.image)
    if args.from_image:
        src = open(args.from_image, 'rb').read()
        first = args.from_zone
        payloads = [read_zone_data(src, first + k) for k in range(args.zones)]
    elif args.from_file:
        blob = open(args.from_file, 'rb').read()
        payloads = [blob[k * DATA:(k + 1) * DATA] for k in range(args.zones)]
    else:
        sys.exit("нужен --from-image или --from-file")
    _write_payloads(args.image, args.zone, fmt, args.raw_zone, payloads)
    check = argparse.Namespace(image=args.image, zone=args.zone, zones=args.zones,
                               format=fmt, raw_zone=args.raw_zone)
    return cmd_verify(check)


def cmd_mkdisk(args) -> int:
    """Создать отформатированный пустой образ дисковода заданного типа."""
    fmt = args.format
    zones = args.zones or CAPACITY[fmt]
    volume = args.volume
    if os.path.exists(args.image) and not args.force:
        sys.exit(f"{args.image} уже существует (--force для перезаписи)")
    w1 = magic_word(volume)
    with open(args.image, 'wb') as f:
        for z in range(zones):
            t0 = 2 * z if fmt == '7m' else z
            hdr = bytearray(64)
            for wi, tr in ((0, t0), (4, t0 + 1)):
                hdr[wi * 8:wi * 8 + 8] = (tr << 36).to_bytes(8, 'little')
            for wi in (1, 5):
                hdr[wi * 8:wi * 8 + 8] = w1.to_bytes(8, 'little')
            f.write(bytes(hdr))
            f.write(b'\x00' * DATA)
    print(f"{args.image}: создан образ {fmt}, {zones} зон, том {volume}; "
          f"резерв: {args.image + '.bak-zones' if os.path.exists(args.image + '.bak-zones') else '—'}")
    return 0


def cmd_selftest(args) -> int:
    import tempfile
    tmp = tempfile.mkdtemp(prefix='zones-selftest-')
    fails = 0
    for fmt in ('7m', '29m'):
        zones = CAPACITY[fmt]
        path = os.path.join(tmp, f'disk-{fmt}')
        with open(path, 'wb') as f:               # пустой образ нужной ёмкости
            f.write(b'\x00' * (zones * ZONE))
        payloads = [bytes((k * 8192 + i) % 256 for i in range(DATA)) for k in range(3)]
        for k, p in enumerate(payloads):
            pz = pult_to_phys(0o1044 + k, False)
            image = bytearray(open(path, 'rb').read())
            hdr = build_header(zone_header(image, pz), pz, fmt, p)
            image[pz * ZONE:pz * ZONE + 64] = hdr
            image[pz * ZONE + 64:(pz + 1) * ZONE] = p
            open(path, 'wb').write(image)
        ns = argparse.Namespace(image=path, zone=0o1044, zones=3, format=fmt, raw_zone=False)
        if cmd_verify(ns) != 0:
            fails += 1
        # round-trip данных
        back = os.path.join(tmp, f'back-{fmt}')
        cmd_read(argparse.Namespace(image=path, zone=0o1044, zones=3,
                                    to_file=back, raw_zone=False))
        got = open(back, 'rb').read()
        if got != b''.join(payloads):
            print(f"{fmt}: данные не совпали при чтении")
            fails += 1
        # запись из файла
        blob = os.path.join(tmp, f'blob-{fmt}')
        open(blob, 'wb').write(b''.join(payloads))
        path2 = os.path.join(tmp, f'disk2-{fmt}')
        shutil.copyfile(path, path2)
        rc = cmd_write(argparse.Namespace(image=path2, zone=0o1044, zones=3,
                                          format=fmt, raw_zone=False,
                                          from_image=None, from_file=blob))
        if rc != 0:
            fails += 1
        print(f"[{fmt}] проверено: дорожки, КС, чтение, запись из файла")
    print("ИТОГ:", "ВСЕ ТЕСТЫ ОК" if fails == 0 else f"ПРОВАЛОВ {fails}")
    return 0 if fails == 0 else 1


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)

    def common(sp):
        sp.add_argument('image')
        sp.add_argument('--zone', type=zone_arg, default=0,
                        help='номер зоны в нумерации ПУЛЬТа (по умолчанию +4 к физической)')
        sp.add_argument('--zones', type=int, default=1)
        sp.add_argument('--format', choices=('7m', '29m'))
        sp.add_argument('--raw-zone', action='store_true',
                        help='--zone задан физическим номером (без сдвига +4)')

    common(sub.add_parser('info'))
    common(sub.add_parser('verify'))
    r = sub.add_parser('read'); common(r); r.add_argument('--to-file', required=True)
    w = sub.add_parser('write'); common(w)
    w.add_argument('--from-image'); w.add_argument('--from-zone', type=zone_arg, default=0)
    w.add_argument('--from-file')
    m = sub.add_parser('mkdisk')
    m.add_argument('image')
    m.add_argument('--format', choices=('7m', '29m'), required=True)
    m.add_argument('--zones', type=int)
    m.add_argument('--volume', type=int, default=0)
    m.add_argument('--force', action='store_true')
    sub.add_parser('selftest')

    args = p.parse_args()
    return {'info': cmd_info, 'verify': cmd_verify, 'read': cmd_read,
            'write': cmd_write, 'mkdisk': cmd_mkdisk,
            'selftest': cmd_selftest}[args.cmd](args)


if __name__ == '__main__':
    sys.exit(main())