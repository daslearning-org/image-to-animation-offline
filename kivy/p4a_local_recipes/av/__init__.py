from pythonforandroid.toolchain import Recipe
from pythonforandroid.recipe import CythonRecipe
from pythonforandroid.logger import info
import os, shutil

class PyAVRecipe(CythonRecipe):

    name = "av"
    version = "13.1.0"
    url = "https://github.com/PyAV-Org/PyAV/archive/v{version}.zip"

    depends = ["python3", "cython", "ffmpeg", "av_codecs"]
    opt_depends = ["openssl"]
    patches = ['patches/compilation_syntax_errors.patch']
    cythonize = True
    cythonize_flags = ["--directive", "language_level=3"]

    def prebuild_arch(self, arch):
        super().prebuild_arch(arch)

        # Paths
        build_dir = self.get_build_dir(arch.arch)
        av_pkg_dir = os.path.join(build_dir, "av")
        include_dir = os.path.join(build_dir, "include")
        # Copy all .pxd files from include -> av/
        info(f"Copying PyAV packages from {include_dir} to {av_pkg_dir}")
        shutil.copytree(include_dir, av_pkg_dir, dirs_exist_ok=True)

    def get_recipe_env(self, arch, with_flags_in_cc=True):
        env = super().get_recipe_env(arch, with_flags_in_cc)

        ffmpeg_build = Recipe.get_recipe("ffmpeg", self.ctx).get_build_dir(arch.arch)
        ffmpeg_include = os.path.join(ffmpeg_build, "include")
        ffmpeg_lib = os.path.join(ffmpeg_build, "lib")
        av_build = self.get_build_dir(arch.arch)
        av_pkg_dir = os.path.join(av_build, "av")
        av_include = os.path.join(av_build, "include")

        # Add to compiler flags
        env["CFLAGS"] += f" -I{ffmpeg_include} -I{av_include}"
        env["CXXFLAGS"] += f" -I{ffmpeg_include} -I{av_include}"
        env["LDFLAGS"] += f" -L{ffmpeg_lib}"

        #self.setup_extra_args = [f"--ffmpeg-dir={ffmpeg_build}"]
        return env


recipe = PyAVRecipe()

# github issue: https://github.com/kivy/python-for-android/issues/3197