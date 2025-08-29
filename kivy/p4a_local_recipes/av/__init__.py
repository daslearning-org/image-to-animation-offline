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
        codec_dir = os.path.join(av_pkg_dir, "codec")

        # Copy all .pxd files from include -> av/
        info("Copying PyAV packages from {} to {}".format(include_dir, av_pkg_dir))
        shutil.copytree(include_dir, av_pkg_dir, dirs_exist_ok=True)

        # Copy libav.pxd to av/codec/ for context.pxd
        #libav_pxd_src = os.path.join(av_pkg_dir, "libav.pxd")
        #libav_pxd_dest = os.path.join(codec_dir, "libav.pxd")
        #if os.path.exists(libav_pxd_src) and os.path.exists(codec_dir):
        #    info("Copying {} to {}".format(libav_pxd_src, libav_pxd_dest))
        #    shutil.copy2(libav_pxd_src, libav_pxd_dest)
        #else:
        #    warning("Could not copy libav.pxd: source ({}) or dest dir ({}) missing".format(libav_pxd_src, codec_dir))

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
            
            # Fix the line causing the error
            content = content.replace(
                'format.name = optr.name if optr else iptr.name',
                'format.name = optr.name.decode("utf-8") if optr else iptr.name.decode("utf-8")'
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
            
            # Fix the line causing the error
            content = content.replace(
                'name = <str>c_name if c_name is not NULL else ""',
                'name = c_name.decode("utf-8") if c_name is not NULL else ""'
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
            
            # Fix the line causing the error
            content = content.replace(
                '<str>url if url is not NULL else ""',
                'url.decode("utf-8") if url is not NULL else ""'
            )

            with open(core_pyx_path, 'w') as f:
                f.write(content)
        else:
            warning("core.pyx not found at {} - patch skipped".format(core_pyx_path))


    def get_recipe_env(self, arch, with_flags_in_cc=True):
        env = super().get_recipe_env(arch)
        env['CYTHON_FLAGS'] = '-3str'
        build_dir = self.get_build_dir(arch.arch)
        av_pkg_dir = os.path.join(build_dir, "av")
        env['CYTHONPATH'] = av_pkg_dir

        build_dir = Recipe.get_recipe("ffmpeg", self.ctx).get_build_dir(
            arch.arch
        )
        self.setup_extra_args = ["--ffmpeg-dir={}".format(build_dir)]

        return env


recipe = PyAVRecipe()