from pythonforandroid.toolchain import Recipe, current_directory, shprint
from os.path import exists, join, realpath
import sh


class FFMpegRecipe(Recipe):
    version = 'n6.1.2'
    url = 'https://github.com/FFmpeg/FFmpeg/archive/{version}.zip'
    depends = ['sdl2', 'libx264', 'ffpyplayer_codecs']
    opts_depends = ['openssl', 'av_codecs']
    patches = ['patches/configure.patch', 'patches/ffmpeg_main.patch']

    def should_build(self, arch):
        build_dir = self.get_build_dir(arch.arch)
        return not exists(join(build_dir, 'lib', 'libffmpeg.so'))

    def get_recipe_env(self, arch):
        env = super().get_recipe_env(arch)
        env['NDK'] = self.ctx.ndk_dir
        return env

    def build_arch(self, arch):
        with current_directory(self.get_build_dir(arch.arch)):
            env = arch.get_env()

            flags = []
            cflags = []
            ldflags = []

            # enable JNI + MediaCodec
            flags += [
                '--enable-jni',
                '--enable-mediacodec'
            ]

            if 'openssl' in self.ctx.recipe_build_order:
                flags += [
                    '--enable-openssl',
                    '--enable-nonfree',
                    '--enable-protocol=https,tls_openssl',
                ]
                build_dir = Recipe.get_recipe('openssl', self.ctx).get_build_dir(arch.arch)
                cflags += ['-I' + build_dir + '/include/',
                           '-DOPENSSL_API_COMPAT=0x10002000L']
                ldflags += ['-L' + build_dir]

            codecs_opts = {"ffpyplayer_codecs", "av_codecs"}
            if codecs_opts.intersection(self.ctx.recipe_build_order):
                flags += ['--enable-gpl']

                # libx264
                flags += ['--enable-libx264']
                build_dir = Recipe.get_recipe('libx264', self.ctx).get_build_dir(arch.arch)
                cflags += ['-I' + build_dir + '/include/']
                ldflags += [build_dir + '/lib/libx264.a']

                # libshine
                flags += ['--enable-libshine']
                build_dir = Recipe.get_recipe('libshine', self.ctx).get_build_dir(arch.arch)
                cflags += ['-I' + build_dir + '/include/']
                ldflags += ['-lshine', '-L' + build_dir + '/lib/', '-lm']

                # libvpx
                flags += ['--enable-libvpx']
                build_dir = Recipe.get_recipe('libvpx', self.ctx).get_build_dir(arch.arch)
                cflags += ['-I' + build_dir + '/include/']
                ldflags += ['-lvpx', '-L' + build_dir + '/lib/']

                # enable useful codecs
                flags += [
                    '--enable-parser=aac,ac3,h261,h264,mpegaudio,mpeg4video,mpegvideo,vc1',
                    '--enable-decoder=aac,h264,mpeg4,mpegvideo',
                    '--enable-encoder=h264,libx264,h264_mediacodec,mpeg4,mpeg2video,libvpx',
                    '--enable-muxer=h264,mov,mp4,mpeg2video,avi',
                    '--enable-demuxer=aac,h264,m4v,mov,mpegvideo,vc1,rtsp',
                ]

            # prevent symbol issues
            flags += ['--disable-symver']

            # instead of disabling programs entirely,
            # build ffmpeg.c into a shared library
            flags += [
                '--disable-doc',
                '--enable-shared',
                '--disable-static',
                '--disable-debug',
                '--enable-small',
                '--enable-cross-compile',
                '--target-os=android',
                '--prefix={}'.format(realpath('.')),
            ]

            # architecture flags
            if 'arm64' in arch.arch:
                arch_flag = 'aarch64'
            elif 'x86' in arch.arch:
                arch_flag = 'x86'
                flags += ['--disable-asm']
            else:
                arch_flag = 'arm'

            flags += [
                '--cross-prefix={}-'.format(arch.target),
                '--arch={}'.format(arch_flag),
                '--strip={}'.format(self.ctx.ndk.llvm_strip),
                '--sysroot={}'.format(self.ctx.ndk.sysroot),
                '--enable-pic',
            ]

            if arch_flag == 'arm':
                cflags += [
                    '-mfpu=vfpv3-d16',
                    '-mfloat-abi=softfp',
                    '-fPIC',
                ]

            env['CFLAGS'] += ' ' + ' '.join(cflags)
            env['LDFLAGS'] += ' ' + ' '.join(ldflags)

            # configure
            configure = sh.Command('./configure')
            shprint(configure, *flags, _env=env)

            # build libraries
            shprint(sh.make, '-j4', _env=env)

            # build ffmpeg.c into a shared library exporting ffmpeg_main
            shprint(sh.make, 'libffmpeg.so', _env=env)

            # install .so files into libs dir
            sh.cp('-a', sh.glob('./lib*.so'),
                  self.ctx.get_libs_dir(arch.arch))


recipe = FFMpegRecipe()
