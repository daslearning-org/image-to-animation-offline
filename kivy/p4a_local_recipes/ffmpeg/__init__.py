from pythonforandroid.toolchain import Recipe, current_directory, shprint
from os.path import exists, join, realpath
import sh
import os


class FFMpegRecipe(Recipe):
    version = 'n6.1.2'
    url = 'https://github.com/FFmpeg/FFmpeg/archive/{version}.zip'
    depends = ['sdl2', 'libx264', 'ffpyplayer_codecs']
    opts_depends = ['openssl', 'av_codecs']
    patches = ['patches/configure.patch']

    def should_build(self, arch):
        build_dir = self.get_build_dir(arch.arch)
        return not exists(join(build_dir, 'lib', 'libavcodec.so'))

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

            # enable hardware acceleration codecs
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
                build_dir = Recipe.get_recipe(
                    'openssl', self.ctx).get_build_dir(arch.arch)
                cflags += ['-I' + build_dir + '/include/',
                           '-DOPENSSL_API_COMPAT=0x10002000L']
                ldflags += ['-L' + build_dir]

            codecs_opts = {"ffpyplayer_codecs", "av_codecs"}
            if codecs_opts.intersection(self.ctx.recipe_build_order):
                flags += ['--enable-gpl']

                # libx264
                flags += ['--enable-libx264']
                build_dir = Recipe.get_recipe(
                    'libx264', self.ctx).get_build_dir(arch.arch)
                cflags += ['-I' + build_dir + '/include/']
                ldflags += [build_dir + '/lib/' + 'libx264.a']

                # libshine
                flags += ['--enable-libshine']
                build_dir = Recipe.get_recipe('libshine', self.ctx).get_build_dir(arch.arch)
                cflags += ['-I' + build_dir + '/include/']
                ldflags += ['-lshine', '-L' + build_dir + '/lib/', '-lm']

                # libvpx
                flags += ['--enable-libvpx']
                build_dir = Recipe.get_recipe(
                    'libvpx', self.ctx).get_build_dir(arch.arch)
                cflags += ['-I' + build_dir + '/include/']
                ldflags += ['-lvpx', '-L' + build_dir + '/lib/']

                # Enable codecs
                flags += [
                    '--enable-parser=aac,ac3,h261,h264,mpegaudio,mpeg4video,mpegvideo,vc1',
                    '--enable-decoder=aac,h264,mpeg4,mpegvideo',
                    '--enable-encoder=h264,libx264,h264_mediacodec,mpeg4,mpeg2video,libvpx',
                    '--enable-muxer=h264,mov,mp4,mpeg2video,avi',
                    '--enable-demuxer=aac,h264,m4v,mov,mpegvideo,vc1,rtsp',
                ]
            else:
                flags += [
                    '--enable-parser=aac,ac3,h261,h264,mpegaudio,mpeg4video,mpegvideo,vc1',
                    '--enable-decoder=aac,h264,mpeg4,mpegvideo',
                    '--enable-encoder=h264,libx264,h264_mediacodec,mpeg4,mpeg2video',
                    '--enable-muxer=h264,mov,mp4,mpeg2video,avi',
                    '--enable-demuxer=aac,h264,m4v,mov,mpegvideo,vc1,rtsp',
                ]

            # prevent _ffmpeg.so version mismatch
            flags += ['--disable-symver']

            # do NOT disable programs anymore → we want ffmpeg binary
            flags += [
                '--disable-doc',
                '--enable-filter=aresample,resample,crop,adelay,volume,scale',
                '--enable-protocol=file,http,hls,udp,tcp',
                '--enable-small',
                '--enable-hwaccels',
                '--enable-pic',
                '--disable-static',
                '--disable-debug',
                '--enable-shared',
            ]

            if 'arm64' in arch.arch:
                arch_flag = 'aarch64'
            elif 'x86' in arch.arch:
                arch_flag = 'x86'
                flags += ['--disable-asm']
            else:
                arch_flag = 'arm'

            # android toolchain
            flags += [
                '--target-os=android',
                '--enable-cross-compile',
                '--cross-prefix={}-'.format(arch.target),
                '--arch={}'.format(arch_flag),
                '--strip={}'.format(self.ctx.ndk.llvm_strip),
                '--sysroot={}'.format(self.ctx.ndk.sysroot),
                '--enable-neon',
                '--prefix={}'.format(realpath('.')),
            ]

            if arch_flag == 'arm':
                cflags += [
                    '-mfpu=vfpv3-d16',
                    '-mfloat-abi=softfp',
                    '-fPIC',
                ]

            env['CFLAGS'] += ' ' + ' '.join(cflags)
            env['LDFLAGS'] += ' ' + ' '.join(ldflags)

            # build & install
            configure = sh.Command('./configure')
            shprint(configure, *flags, _env=env)
            shprint(sh.make, '-j4', _env=env)
            shprint(sh.make, 'install', _env=env)

            # copy libs
            sh.cp('-a', sh.glob('./lib/lib*.so'),
                  self.ctx.get_libs_dir(arch.arch))

            # copy ffmpeg binary into app/bin
            bin_dir = join(self.ctx.get_python_install_dir(arch.arch), 'ffmpeg_bin')
            os.makedirs(bin_dir, exist_ok=True)
            if exists('./ffmpeg'):
                sh.cp('./ffmpeg', bin_dir)


recipe = FFMpegRecipe()