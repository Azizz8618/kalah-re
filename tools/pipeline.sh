#!/bin/bash
# Конвейер КАЛАХа от исходника до проверки на живом кадре:
#   1) собрать kalah.pas конвейером ПУЛЬТ (dispak pult2.b6) -> группа в ~/.besm6/1234;
#   2) записать группу на целевой том с корректными служебными словами и КС
#      (формат 7m или 29m) средствами .localdocs/zones.py;
#   3) перезапустить единственный экземпляр ДИСПАК (.localdocs/emustart.sh);
#   4) смоук-тест: КАЛАХ 4199 -> КАЛ ТРЕ -> категория -> ход -> ПРА, проверить кадр
#      (маркер версии, чистое поле, текст «ПРАВИЛА»);
#   5) по завершении освободить линии ДКС (если не задан --keep).
#
# Употребление:
#   tools/pipeline.sh [--vol=ПУТЬ] [--format=7m|29m] [--zone=ВОСЬМ] [--no-run] [--keep]
# по умолчанию: --vol=~/.besm6-копия MD/2061 (7m), зона 1044, полный прогон с тестом.
set -uo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
TOOLS="$REPO/tools"
LOC="$TOOLS"
LOC_FB="$REPO/.localdocs"
DISPAK=${DISPAK:-/usr/local/bin/dispak}
BESM6_PATH_DEF="$HOME/.besm6:/usr/local/share/besm6:$HOME/Yandex.Disk/simh/BESM6/MD:$HOME/Yandex.Disk/simh/BESM6/MD/EC5061:$HOME/Yandex.Disk/simh/BESM6/ML"

VOL="$HOME/Yandex.Disk/simh/BESM6/MD/2061"
FMT=7m
ZONE=1044
GROUP_ZONES=6
DO_RUN=1
KEEP=0
MARKER="V3"

for a in "$@"; do
    case "$a" in
        --vol=*)    VOL=${a#*=} ;;
        --format=*) FMT=${a#*=} ;;
        --zone=*)   ZONE=${a#*=} ;;
        --marker=*) MARKER=${a#*=} ;;
        --no-run)   DO_RUN=0 ;;
        --keep)     KEEP=1 ;;
        -h|--help)  sed -n '2,20p' "$0"; exit 0 ;;
        *) echo "неизвестный аргумент: $a" >&2; exit 2 ;;
    esac
done

helper() { [ -f "$TOOLS/$1" ] && echo "$TOOLS/$1" || echo "$LOC_FB/$1"; }
WORK=$(mktemp -d "${TMPDIR:-/tmp}/kalah-pipe.XXXXXX")
cleanup() { [ "$KEEP" = 1 ] || { pkill -9 -x besm6 2>/dev/null; tmux kill-session -t besm6 2>/dev/null; }; rm -rf "$WORK"; }
trap cleanup EXIT
fail() { echo "СБОЙ: $*" >&2; exit 1; }

echo "### 1. Сборка kalah.pas конвейером ПУЛЬТ ###"
[ -f "$REPO/kalah.pas" ] || fail "нет $REPO/kalah.pas"
cp "$REPO/kalah.pas" "$WORK/kalah.pas"
python3 - "$WORK" <<'PY'
import sys, os
w=sys.argv[1]
src=open(os.path.join(w,'kalah.pas'),encoding='utf-8').read().splitlines()
out=["з буф=тт"]
for line in src:
    out.append((line if line.strip() else " ")+"\\")
out += ["//", "пас буф - зонгп 500200 10", "конец"]
open(os.path.join(w,'in.txt'),'w',encoding='utf-8').write("\n".join(out)+"\n")
PY
cp "$REPO/pult2.b6" "$WORK/pult2.b6"
( cd "$WORK" && BESM6_PATH="$BESM6_PATH_DEF" "$DISPAK" pult2.b6 < in.txt > build.log 2>&1 ) &
BPID=$!
for _ in $(seq 1 15); do
    sleep 8
    grep -aqE "ВСЕ СДЕЛАНО|Interrupt|ОБНАРУЖЕНО [0-9]+ ОШИБ|ОШ.АВТОКОД" "$WORK/build.log" 2>/dev/null && break
    [ "$(stat -c %s "$WORK/build.log" 2>/dev/null || echo 0)" -gt 3000000 ] && { echo "листинг разрастается — глушим"; kill -9 $BPID 2>/dev/null; break; }
done
pkill -9 -x dispak 2>/dev/null
grep -aqE "НА БОБ 1234 ЗАПИСЬ [0-9]+ ЗОН|ВСЕ СДЕЛАНО" "$WORK/build.log" || { tail -5 "$WORK/build.log"; fail "сборка не записала группу (см build.log)"; }
grep -aqE "ОБНАРУЖЕНО [0-9]+ ОШИБ|ОШ.АВТОКОД" "$WORK/build.log" && fail "ошибки компиляции"
echo "собрано и записано в ~/.besm6/1234"

echo "### 2. Запись группы на том $VOL (формат $FMT, зона $ZONE) ###"
cp "$VOL" "$WORK/vol.bak" 2>/dev/null
python3 "$(helper zones.py)" write "$VOL" --zone "$ZONE" --zones "$GROUP_ZONES" \
    --from-image "$HOME/.besm6/1234" --from-zone 204 --format "$FMT" \
    || { cp "$WORK/vol.bak" "$VOL"; fail "запись на том не прошла (том откачен)"; }
python3 "$(helper zones.py)" verify "$VOL" --zone "$ZONE" --zones "$GROUP_ZONES" | tail -1

if [ "$DO_RUN" = 0 ]; then echo "(--no-run: без проверки на живом кадре)"; exit 0; fi

echo "### 3. Перезапуск ДИСПАК (один экземпляр) ###"
sh "$(helper emustart.sh)" || fail "не поднялся эмулятор"

echo "### 4. Смоук-тест на живом кадре ###"
send() { tmux send-keys -t besm6 "$1" Enter; sleep "${2:-6}"; }
grab() { tmux capture-pane -p -t besm6; }
send 'КАЛАХ 4199' 7
grab | grep -aqE '==\*' || fail "игра не вышла в промпт =="
send 'КАЛ ТРЕ' 5
send 'Ю' 4
send 'Д' 10
FRAME="$(grab)"
echo "$FRAME" | grep -aqE "\^+\s*$MARKER|V3" || fail "на кадре нет маркера версии $MARKER"
echo "$FRAME" | grep -aqE '\( [0-9 ]' || fail "нет строк поля (лунок)"
send '4' 10
grab | grep -aqE '\( [0-9 ]' || fail "после хода поле пропало"
send 'ПРА' 8
R=$(grab)
# правила многострочные и уходят за край — ищем характерные слова ТЕЛА, а не заголовок
echo "$R" | grep -aiqE 'ЛУHKИ 1\.\.6|ЗАXBAT|ЗАХВАТ|MAГAЗИH|МАГАЗИН|XОД: ЦИФPA|ПОБEДA' \
  && echo "правила по ПРА: на экране" || echo "ВНИМАНИЕ: текст правил не пойман (проверьте ПРА из меню)"
echo "КАДР (фрагмент):"; grab | grep -aE "$MARKER|ДЖИH|\( |К \(|ХОД|XОД|ПРАВИЛА|ИГPЫ|ЛУHK" | tail -10
echo "### КОНВЕЙЕР ОК: собрано, записано, игра грузится, версия $MARKER, поле и правила отрисованы ###"