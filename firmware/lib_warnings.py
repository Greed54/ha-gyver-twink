# PlatformIO pre-script: treat third-party library headers as system headers.
# FastLED 3.4 and the bundled GyverLibs are kept unmodified; their headers
# produce hundreds of warnings (-Wregister etc.) in every file that includes
# them. GCC ignores -I for a directory also given with -isystem, so the
# warnings from these headers are silenced while the sketch keeps -Wall.
import os

Import("env")  # noqa: F821  (provided by SCons)

dirs = [os.path.join(env.subst("$PROJECT_LIBDEPS_DIR"), env.subst("$PIOENV"), "FastLED", "src")]
lib_dir = env.subst("$PROJECT_DIR/lib")
dirs += [os.path.join(lib_dir, name, "src") for name in sorted(os.listdir(lib_dir))]

for path in dirs:
    env.Append(CCFLAGS=["-isystem", path])
