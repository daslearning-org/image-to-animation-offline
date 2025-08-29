from pythonforandroid.toolchain import Recipe
from pythonforandroid.recipe import CythonRecipe
import os


class PyAVRecipe(CythonRecipe):

    name = "av"
    version = "10.0.0"
    url = "https://github.com/PyAV-Org/PyAV/archive/v{version}.zip"

    depends = ["python3", "cython", "ffmpeg", "av_codecs"]
    opt_depends = ["openssl"]

    def get_recipe_env(self, arch, with_flags_in_cc=True):
        env = super().get_recipe_env(arch)

        ffmpeg_build = Recipe.get_recipe("ffmpeg", self.ctx).get_build_dir(arch.arch)

        ffmpeg_include = os.path.join(ffmpeg_build, "include")
        ffmpeg_lib = os.path.join(ffmpeg_build, "lib")

        # Tell compiler where to look
        env["CFLAGS"] = env.get("CFLAGS", "") + f" -I{ffmpeg_include}"
        env["LDFLAGS"] = env.get("LDFLAGS", "") + f" -L{ffmpeg_lib}"

        # Some setup.py use this argument
        self.setup_extra_args = [f"--ffmpeg-dir={ffmpeg_build}"]

        return env


recipe = PyAVRecipe()
