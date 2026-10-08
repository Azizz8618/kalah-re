# Building and Installation Guide

## Prerequisites

### Required Software

1. **C++ Compiler** with C++17 support
   - GCC 7.0 or later
   - Clang 5.0 or later
   - MSVC 2017 or later (Windows)

2. **ncurses Library**
   - Development headers and libraries

3. **Make** (optional but recommended)
   - GNU Make 3.81 or later

### Installing Dependencies

#### Ubuntu / Debian
```bash
sudo apt-get update
sudo apt-get install build-essential libncurses5-dev libncursesw5-dev
```

#### Fedora / RHEL / CentOS
```bash
sudo dnf install gcc-c++ ncurses-devel
# or on older systems:
sudo yum install gcc-c++ ncurses-devel
```

#### Arch Linux
```bash
sudo pacman -S base-devel ncurses
```

#### macOS
```bash
# Using Homebrew
brew install ncurses

# Using MacPorts
sudo port install ncurses
```

#### Windows (WSL)
Use the Ubuntu/Debian instructions above after installing WSL.

## Building

### Quick Start (using Make)

```bash
# Clone or extract the source code
cd kalah-re

# Build the game
make

# Run the game
./kalah
```

### Manual Compilation

If you don't have `make` or prefer manual compilation:

```bash
g++ -std=c++17 -Wall -Wextra -O2 -c kalah.cpp -o kalah.o
g++ -std=c++17 -Wall -Wextra -O2 -c ui.cpp -o ui.o
g++ -std=c++17 -Wall -Wextra -O2 -c main.cpp -o main.o
g++ -std=c++17 -Wall -Wextra -O2 -o kalah kalah.o ui.o main.o -lncurses
```

### Build Options

#### Debug Build
```bash
make clean
make CXXFLAGS="-std=c++17 -Wall -Wextra -O0 -g -DDEBUG"
```

#### Optimized Build
```bash
make clean
make CXXFLAGS="-std=c++17 -Wall -Wextra -O3 -march=native -DNDEBUG"
```

#### Static Build (portable binary)
```bash
make LDFLAGS="-lncurses -static"
```

## Building the original `kalah.pas` (BESM-6 / Дубна)

The Pascal source compiles on the Dubna monitor system under the `dispak`
package emulator (`/usr/local/bin/dispak`; see also `~/Yandex.Disk/pascal-re`).
`comp.sh` shows the interaction; a non-interactive equivalent:

```
BESM6_PATH=~/.besm6:/usr/local/share/besm6:~/Yandex.Disk/simh/BESM6/MD:~/Yandex.Disk/simh/BESM6/MD/EC5061:~/Yandex.Disk/simh/BESM6/ML \
  dispak pult2.b6 < deck.txt
```

`deck.txt` = `з буф=тт`, then each source line with a trailing `\`, then `//`,
then `пас буф - зонгп 500200 10` (compile to the scratch volume 1234, zone 0200
octal) and `конец`. The compiler is `ПАСКАЛЬ-АВТОКОД 9.(17.05.88)`; keywords are
written `_program`, `_if`, ... with `_( ... _)` blocks, and identifiers are
significant to 6 characters. `зонгп <ЛУ><зона> <число зон>` links and writes the
group (header `000КАЛАХ <дата> 00010]` plus relocatable-free object). To place the
game next to the lunar-lander program, mount volume 2061 with
`лент 51(2061-ЗП)^` in the boot deck and use `зонгп 511044 10` (the `LАNDIN`
group occupies zones 1042-1043 octal there). Check the result with
`besmtool view 2061 --start=548 --encoding=g,k` and reassemble with `reasm.sh`
plus `./dtran -n -E entry.txt -d` to compare against the reference object.
Only ever write to working copies under `~/.besm6/`; keep backups before
touching any volume image.

## Verification

After building, verify the installation:

```bash
# Check if the binary exists
ls -lh kalah

# Test run (will launch the game)
./kalah
```

## Troubleshooting

### "ncurses.h: No such file or directory"

**Problem**: ncurses development headers not found.

**Solution**:
```bash
# Ubuntu/Debian
sudo apt-get install libncurses5-dev

# Fedora/RHEL
sudo dnf install ncurses-devel
```

### "undefined reference to 'initscr'"

**Problem**: Linker cannot find ncurses library.

**Solution**: Make sure `-lncurses` is in the link command:
```bash
g++ -o kalah *.o -lncurses
```

### Compiler version too old

**Problem**: `error: #error This file requires compiler and library support for the ISO C++ 2017 standard`

**Solution**: Update your compiler or use a newer version:
```bash
# Check version
g++ --version

# On Ubuntu, install newer GCC
sudo apt-get install g++-9
export CXX=g++-9
make clean && make
```

### Display issues / garbled text

**Problem**: Terminal doesn't support required features.

**Solution**:
1. Use a modern terminal emulator (GNOME Terminal, iTerm2, etc.)
2. Ensure TERM is set correctly:
   ```bash
   echo $TERM
   export TERM=xterm-256color
   ```

### Game doesn't respond to input

**Problem**: Terminal in wrong mode.

**Solution**: Kill the game with Ctrl+C and reset terminal:
```bash
reset
# or
stty sane
```

## Platform-Specific Notes

### macOS
If using Homebrew's ncurses:
```bash
export CPATH=/usr/local/opt/ncurses/include
export LIBRARY_PATH=/usr/local/opt/ncurses/lib
make
```

### Windows (Cygwin)
```bash
# Install ncurses through Cygwin setup
# Then build normally
make
```

### Windows (MinGW)
Use pdcurses instead of ncurses:
```bash
# Install pdcurses
# Modify Makefile: change -lncurses to -lpdcurses
make
```

## Cleaning Build Files

```bash
# Remove object files and binary
make clean

# Remove everything (including backups)
make clean
rm -f *~ *.bak
```

## Installation

### System-wide installation
```bash
sudo make install
# This installs to /usr/local/bin by default
```

### User installation
```bash
mkdir -p ~/bin
cp kalah ~/bin/
# Add ~/bin to PATH if needed
```

## Running

```bash
# From build directory
./kalah

# If installed system-wide
kalah

# With specific terminal size
TERM=xterm-256color ./kalah
```

## Performance Tips

1. **Release build**: Use `-O2` or `-O3` optimization
2. **Native optimization**: Add `-march=native` for CPU-specific optimizations
3. **Link-time optimization**: Add `-flto` for whole-program optimization

Example:
```bash
make CXXFLAGS="-std=c++17 -O3 -march=native -flto" LDFLAGS="-lncurses -flto"
```

## Development

### Rebuilding after changes

```bash
# Rebuild everything
make clean && make

# Rebuild only changed files
make
```

### Code formatting (if you have clang-format)
```bash
clang-format -i *.cpp *.h
```

### Running with valgrind (memory leak check)
```bash
valgrind --leak-check=full ./kalah
```

## Getting Help

If you encounter issues:

1. Check this troubleshooting guide
2. Verify all dependencies are installed
3. Check terminal compatibility
4. Try a debug build for more information
5. Check the README.md for game-specific help

## Success!

If everything built successfully, you should see:
```
$ ./kalah
[Game launches with welcome screen]
```

Enjoy playing Kalah!
