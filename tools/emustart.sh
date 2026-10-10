#!/bin/sh
# Перезапуск ОДНОГО экземпляра SIMH-ДИСПАК: снять все «висящие» экземпляры
# (процесс эмулятора переживает закрытие tmux-сессии и продолжает держать
# порты 4199/4202-4223 — свежий тогда поднимается БЕЗ линий ДКС) и поднять один.
#
#   emustart.sh          — перезапустить
#   emustart.sh status   — только показать состояние (ничего не трогая)
set -eu

OSZAGR="$HOME/Yandex.Disk/simh/BESM6/OSZAGR"
SESSION=besm6

# Имя процесса — ровно "besm6" (argv[0] = ../../BIN/besm6), поэтому -x
# (точное совпадение по имени) не задевает оболочку, запустившую скрипт.
status() {
    n=$(pgrep -xc besm6 2>/dev/null || echo 0)
    p=$(ss -tln 2>/dev/null | grep -cE ':4199|:42[0-2][0-9]' || true)
    echo "экземпляров besm6: $n; линий ДКС слушает: $p"
}

if [ "${1:-}" = status ]; then status; exit 0; fi

pkill -9 -x besm6 2>/dev/null || true
tmux kill-session -t "$SESSION" 2>/dev/null || true
# эмулятор не всегда умирает по TERM и продолжает держать порты — ждём,
# пока линии освободятся, иначе свежий поднимется без ДКС
for _ in 1 2 3 4 5 6 7 8 9 10; do
    p=$(ss -tln 2>/dev/null | grep -cE ':4199|:42[0-2][0-9]' || true)
    [ "$p" = 0 ] && break
    sleep 1
done

cd "$OSZAGR"
# Все 23 линии должны подняться: если хоть одна занята сокетом прежнего
# экземпляра (TIME_WAIT), её attach молча не срабатывает — перезапускаем.
for attempt in 1 2 3; do
    tmux new-session -d -s "$SESSION" -c "$OSZAGR" '../../BIN/besm6 dispak.ini'
    sleep 30
    p=$(ss -tln 2>/dev/null | grep -cE ':4199|:42[0-2][0-9]' || true)
    [ "$p" = 23 ] && break
    echo "линий $p из 23 — перезапуск (попытка $attempt)"
    pkill -9 -x besm6 2>/dev/null || true
    tmux kill-session -t "$SESSION" 2>/dev/null || true
    sleep 8
done
status
echo "консоль: tmux attach -t $SESSION"