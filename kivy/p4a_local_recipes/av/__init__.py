from pythonforandroid.toolchain import Recipe
from pythonforandroid.recipe import CythonRecipe
from pythonforandroid.logger import info, warning
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
        setup_py_path = os.path.join(build_dir, "setup.py")

        # Copy all from include -> av/
        #info("Copying PyAV packages from {} to {}".format(include_dir, av_pkg_dir))
        #shutil.copytree(include_dir, av_pkg_dir, dirs_exist_ok=True)

        # Patch dictionary.pyx for str -> bytes coercion
        dict_pyx_path = os.path.join(av_pkg_dir, 'dictionary.pyx')
        if os.path.exists(dict_pyx_path):
            info("Patching {} for Python 3 string handling".format(dict_pyx_path))
            with open(dict_pyx_path, 'r') as f:
                content = f.read()
            
            # Fix av_dict_get and av_dict_set calls
            content = content.replace(
                'lib.av_dict_get(self.ptr, key, NULL, 0)',
                'lib.av_dict_get(self.ptr, key.encode("utf-8"), NULL, 0)'
            )
            content = content.replace(
                'lib.av_dict_set(self.ptr, key, value, 0)',
                'lib.av_dict_set(self.ptr, key.encode("utf-8"), value.encode("utf-8"), 0)'
            )

            with open(dict_pyx_path, 'w') as f:
                f.write(content)
        else:
            warning("dictionary.pyx not found at {} - patch skipped".format(dict_pyx_path))

        # Patch format.pyx for const char* -> str decoding
        format_pyx_path = os.path.join(av_pkg_dir, 'format.pyx')
        if os.path.exists(format_pyx_path):
            info("Patching {} for Python 3 string handling".format(format_pyx_path))
            with open(format_pyx_path, 'r') as f:
                content = f.read()
            custom_build_ext = """
import sys
def normalize_url(url):
    fsenc = sys.getfilesystemencoding() or "utf-8"
    if isinstance(url, bytes):
        return url.decode(fsenc)   # bytes → str
    return url
"""
            content = custom_build_ext + "\n" + content
            # Fix the line causing the error
            content = content.replace(
                'format.name = optr.name if optr else iptr.name',
                'format.name = normalize_url(optr.name) if optr else normalize_url(iptr.name)'
            )

            with open(format_pyx_path, 'w') as f:
                f.write(content)
        else:
            warning("format.pyx not found at {} - patch skipped".format(format_pyx_path))

        # Patch logging.pyx for const char* -> str decoding
        logging_pyx_path = os.path.join(av_pkg_dir, 'logging.pyx')
        if os.path.exists(logging_pyx_path):
            info("Patching {} for Python 3 string handling".format(logging_pyx_path))
            with open(logging_pyx_path, 'r') as f:
                content = f.read()
            custom_build_ext = """
import sys
def normalize_url(url):
    fsenc = sys.getfilesystemencoding() or "utf-8"
    if isinstance(url, bytes):
        return url.decode(fsenc)   # bytes → str
    return url
"""
            content = custom_build_ext + "\n" + content
            # Fix the line causing the error
            content = content.replace(
                'name = <str>c_name if c_name is not NULL else ""',
                'name = normalize_url(c_name) if c_name is not NULL else ""'
            )

            with open(logging_pyx_path, 'w') as f:
                f.write(content)
        else:
            warning("logging.pyx not found at {} - patch skipped".format(logging_pyx_path))

        # Patch streams.pyx for AVMediaType comparison
        streams_pyx_path = os.path.join(av_pkg_dir, 'container', 'streams.pyx')
        if os.path.exists(streams_pyx_path):
            info("Patching {} for AVMediaType comparison".format(streams_pyx_path))
            with open(streams_pyx_path, 'r') as f:
                content = f.read()
            
            # Fix type comparison errors by casting codec_type to int
            content = content.replace(
                'stream.ptr.codecpar.codec_type == lib.AVMEDIA_TYPE_VIDEO',
                '<int>stream.ptr.codecpar.codec_type == <int>lib.AVMEDIA_TYPE_VIDEO'
            )
            content = content.replace(
                'stream.ptr.codecpar.codec_type == lib.AVMEDIA_TYPE_AUDIO',
                '<int>stream.ptr.codecpar.codec_type == <int>lib.AVMEDIA_TYPE_AUDIO'
            )
            content = content.replace(
                'stream.ptr.codecpar.codec_type == lib.AVMEDIA_TYPE_SUBTITLE',
                '<int>stream.ptr.codecpar.codec_type == <int>lib.AVMEDIA_TYPE_SUBTITLE'
            )
            content = content.replace(
                'stream.ptr.codecpar.codec_type == lib.AVMEDIA_TYPE_ATTACHMENT',
                '<int>stream.ptr.codecpar.codec_type == <int>lib.AVMEDIA_TYPE_ATTACHMENT'
            )
            content = content.replace(
                'stream.ptr.codecpar.codec_type == lib.AVMEDIA_TYPE_DATA',
                '<int>stream.ptr.codecpar.codec_type == <int>lib.AVMEDIA_TYPE_DATA'
            )

            with open(streams_pyx_path, 'w') as f:
                f.write(content)
        else:
            warning("streams.pyx not found at {} - patch skipped".format(streams_pyx_path))

        # Patch core.pyx for const char* -> str decoding
        core_pyx_path = os.path.join(av_pkg_dir, 'container', 'core.pyx')
        if os.path.exists(core_pyx_path):
            info("Patching {} for Python 3 string handling".format(core_pyx_path))
            with open(core_pyx_path, 'r') as f:
                content = f.read()
            custom_build_ext = """
import sys
def normalize_url(url):
    fsenc = sys.getfilesystemencoding() or "utf-8"
    if isinstance(url, bytes):
        return url.decode(fsenc)   # bytes → str
    return url
"""
            content = custom_build_ext + "\n" + content
            # Fix the line causing the error
            content = content.replace(
                '<str>url if url is not NULL else ""',
                'normalize_url(url) if url is not NULL else ""'
            )

            with open(core_pyx_path, 'w') as f:
                f.write(content)
        else:
            warning("core.pyx not found at {} - patch skipped".format(core_pyx_path))

        # Patch audio/format.pyx for char* -> str decoding
        audio_format_pyx_path = os.path.join(av_pkg_dir, 'audio', 'format.pyx')
        if os.path.exists(audio_format_pyx_path):
            info("Patching {} for Python 3 string handling".format(audio_format_pyx_path))
            with open(audio_format_pyx_path, 'r') as f:
                content = f.read()
            custom_build_ext = """
import sys
def normalize_url(url):
    fsenc = sys.getfilesystemencoding() or "utf-8"
    if isinstance(url, bytes):
        return url.decode(fsenc)   # bytes → str
    return url
"""
            content = custom_build_ext + "\n" + content
            # Fix the line causing the error
            content = content.replace(
                'return <str>lib.av_get_sample_fmt_name(self.sample_fmt)',
                'return normalize_url(lib.av_get_sample_fmt_name(self.sample_fmt))'
            )

            with open(audio_format_pyx_path, 'w') as f:
                f.write(content)
        else:
            warning("audio/format.pyx not found at {} - patch skipped".format(audio_format_pyx_path))

        # Patch video/format.pyx for const char* -> str decoding
        video_format_pyx_path = os.path.join(av_pkg_dir, 'video', 'format.pyx')
        if os.path.exists(video_format_pyx_path):
            info("Patching {} for Python 3 string handling".format(video_format_pyx_path))
            with open(video_format_pyx_path, 'r') as f:
                content = f.read()
            custom_build_ext = """
import sys
def normalize_url(url):
    fsenc = sys.getfilesystemencoding() or "utf-8"
    if isinstance(url, bytes):
        return url.decode(fsenc)   # bytes → str
    return url
"""
            content = custom_build_ext + "\n" + content
            # Fix the line causing the error
            content = content.replace(
                'return <str>self.ptr.name',
                'return normalize_url(self.ptr.name)'
            )

            with open(video_format_pyx_path, 'w') as f:
                f.write(content)
        else:
            warning("video/format.pyx not found at {} - patch skipped".format(video_format_pyx_path))

        # Patch setup.py to add custom build_ext command
        if os.path.exists(setup_py_path):
            info("Patching {} to use custom build_ext for setuptools compatibility".format(setup_py_path))
            with open(setup_py_path, 'r') as f:
                content = f.read()
            
            # Add custom build_ext class at the top of setup.py
            custom_build_ext = """
from setuptools.command.build_ext import build_ext as _build_ext
from distutils.cmd import Command as DistutilsCommand

class custom_build_ext(_build_ext):
    def finalize_options(self):
        super().finalize_options()
        # Ensure compatibility with distutils checks
        self.distribution.ext_modules = self.distribution.ext_modules or []
        # Add distutils compatibility
        self._is_command = True  # Mimic distutils Command behavior
"""
            content = custom_build_ext + "\n" + content
            
            # Modify setup() to use custom_build_ext
            content = content.replace(
                'setup(',
                'setup(cmdclass={"build_ext": custom_build_ext},'
            )

            with open(setup_py_path, 'w') as f:
                f.write(content)
        else:
            warning("setup.py not found at {} - patch skipped".format(setup_py_path))


    def get_recipe_env(self, arch, with_flags_in_cc=True):
        env = super().get_recipe_env(arch)
        env['CYTHON_FLAGS'] = '-3' #'-3str'
        build_dir = self.get_build_dir(arch.arch)
        av_pkg_dir = os.path.join(build_dir, "av")
        include_dir = os.path.join(build_dir, "include")
        env['CYTHONPATH'] = include_dir

        build_dir = Recipe.get_recipe("ffmpeg", self.ctx).get_build_dir(
            arch.arch
        )
        self.setup_extra_args = ["--ffmpeg-dir={}".format(build_dir)]

        return env


recipe = PyAVRecipe()