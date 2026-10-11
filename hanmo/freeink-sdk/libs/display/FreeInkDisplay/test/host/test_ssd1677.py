"""Compile the real SSD1677 driver against a recording bus."""
import pathlib
import shutil
import subprocess
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
DISPLAY = HERE.parents[1]


def run_trace(source=None, includes=()):
    with tempfile.TemporaryDirectory() as directory:
        tmp = pathlib.Path(directory)
        for name in ("driver", "lut"):
            shutil.copytree(DISPLAY / "src" / name, tmp / name)
        shutil.copytree(HERE / "ssd1677_stubs", tmp, dirs_exist_ok=True)
        command = ["c++", "-std=c++17", "-I", str(tmp), "-I", str(HERE),
                   "-I", str(DISPLAY / "include"), "-I",
                   str(DISPLAY.parents[1] / "hardware/BoardConfig/include")]
        for directory in includes:
            command += ["-I", str(directory)]
        binary = tmp / "trace"
        command += [str(source or HERE / "test_ssd1677.cpp"), "-o", str(binary)]
        subprocess.run(command, check=True)
        subprocess.run([str(binary)], check=True)


class Ssd1677Test(unittest.TestCase):
    def test_command_sequences(self):
        run_trace()


if __name__ == "__main__":
    unittest.main()
