# python core modules
import os
os.environ['KIVY_GL_BACKEND'] = 'sdl2'
import sys
from threading import Thread

# kivy world
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.label import MDLabel
from kivymd.uix.button import MDFlatButton, MDFloatingActionButton
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.spinner import MDSpinner
from kivymd.uix.filemanager import MDFileManager
from kivymd.uix.dialog import MDDialog

from kivy.uix.videoplayer import VideoPlayer
from kivy.lang import Builder
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.utils import platform
from kivy.properties import StringProperty, NumericProperty, ObjectProperty
if platform == "android":
    from jnius import autoclass, PythonJavaClass, java_method

# IMPORTANT: Set this property for keyboard behavior
Window.softinput_mode = "below_target"

# Import your local screen classes & modules
from screens.divider import MyMDDivider
from sketchApi import get_split_lens, initiate_sketch

## Global definitions
__version__ = "0.2.2"
# Determine the base path for your application's resources
if getattr(sys, 'frozen', False):
    # Running as a PyInstaller bundle
    base_path = sys._MEIPASS
else:
    # Running in a normal Python environment
    base_path = os.path.dirname(os.path.abspath(__file__))
kv_file_path = os.path.join(base_path, 'main_layout.kv')


# app class
class DlImg2SktchApp(MDApp):
    split_len = NumericProperty(10)
    frame_rate = NumericProperty(25)
    obj_skip_rate = NumericProperty(8)
    bck_skip_rate = NumericProperty(14)
    main_img_duration = NumericProperty(2)
    internal_storage = ObjectProperty()
    external_storage = ObjectProperty()
    video_dir = ObjectProperty()
    split_len_options = ObjectProperty()
    split_len_drp = ObjectProperty
    image_path = StringProperty("")
    vid_download_path = StringProperty("")
    is_cv2_running = ObjectProperty()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Window.bind(on_keyboard=self.events)

    def build(self):
        self.theme_cls.primary_palette = "Blue"
        self.theme_cls.accent_palette = "Orange"
        self.top_menu_items = {
            "Documentation": {
                "icon": "file-document-check",
                "action": "web",
                "url": "https://blog.daslearning.in/llm_ai/genai/image-to-animation.html",
            },
            "Contact Us": {
                "icon": "card-account-phone",
                "action": "web",
                "url": "https://daslearning.in/contact/",
            },
            "Check for update": {
                "icon": "github",
                "action": "update",
                "url": "",
            }
        }
        return Builder.load_file(kv_file_path)

    def on_start(self):

        # paths setup
        if platform == "android":
            from android.permissions import request_permissions, Permission
            sdk_version = 28
            try:
                VERSION = autoclass('android.os.Build$VERSION')
                sdk_version = VERSION.SDK_INT
                print(f"Android SDK: {sdk_version}")
                #self.show_toast_msg(f"Android SDK: {sdk_version}")
            except Exception as e:
                print(f"Could not check the android SDK version: {e}")
            if sdk_version >= 33:  # Android 13+
                permissions = [Permission.READ_MEDIA_IMAGES]
            else:  # Android 9–12
                permissions = [Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE]
            request_permissions(permissions)
            context = autoclass('org.kivy.android.PythonActivity').mActivity
            android_path = context.getExternalFilesDir(None).getAbsolutePath()
            self.video_dir = os.path.join(android_path, 'generated')
            image_dir = os.path.join(android_path, 'images')
            os.makedirs(image_dir, exist_ok=True)
            self.internal_storage = android_path
            try:
                Environment = autoclass("android.os.Environment")
                self.external_storage = Environment.getExternalStorageDirectory().getAbsolutePath()
            except Exception:
                self.external_storage = os.path.abspath("/storage/emulated/0/")
        else:
            self.internal_storage = os.path.abspath("/")
            self.external_storage = os.path.abspath("/")
            self.video_dir = os.path.join(self.user_data_dir, 'generated')
        os.makedirs(self.video_dir, exist_ok=True)
        test_file = os.path.join(self.video_dir, "test.txt")
        try:
            with open(test_file, 'w') as f:
                f.write("Test write")
            print(f"Successfully wrote to {test_file}")
            os.remove(test_file)  # Clean up
        except Exception as e:
            print(f"Failed to write to {test_file}: {e}")

        # file managers
        self.is_img_manager_open = False
        self.img_file_manager = MDFileManager(
            exit_manager=self.img_file_exit_manager,
            select_path=self.select_img_path,
            ext=[".png", ".jpg", ".jpeg", ".webp"],  # Restrict to image files
            selector="file",  # Restrict to selecting files only
            preview=True,
            #show_hidden_files=True,
        )
        self.is_vid_manager_open = False
        self.vid_file_manager = MDFileManager(
            exit_manager=self.vid_file_exit_manager,
            select_path=self.select_vid_path,
            selector="folder",  # Restrict to selecting directories only
        )

        # Menu items
        self.split_len_drp = self.root.ids.split_len_drp
        menu_items = []
        self.split_len_options = MDDropdownMenu(
            md_bg_color="#bdc6b0",
            caller=self.split_len_drp,
            items=menu_items,
        )
        # top menu
        menu_items = [
            {
                "text": menu_key,
                "leading_icon": self.top_menu_items[menu_key]["icon"],
                "on_release": lambda x=menu_key: self.top_menu_callback(x),
                "font_size": sp(36)
            } for menu_key in self.top_menu_items
        ]
        self.menu = MDDropdownMenu(
            items=menu_items,
            width_mult=4,
        )

    def menu_bar_callback(self, button):
        self.menu.caller = button
        self.menu.open()

    def top_menu_callback(self, text_item):
        self.menu.dismiss()
        action = ""
        url = ""
        try:
            action = self.top_menu_items[text_item]["action"]
            url = self.top_menu_items[text_item]["url"]
        except Exception as e:
            print(f"Erro in menu process: {e}")
        if action == "web" and url != "":
            self.open_link(url)
        elif action == "update":
            buttons = [
                MDFlatButton(
                    text="Cancel",
                    theme_text_color="Custom",
                    text_color=self.theme_cls.primary_color,
                    on_release=self.txt_dialog_closer
                ),
                MDFlatButton(
                    text="Releases",
                    theme_text_color="Custom",
                    text_color="green",
                    on_release=self.update_checker
                ),
            ]
            self.show_text_dialog(
                "Check for update",
                f"Your version: {__version__}",
                buttons
            )

    def show_toast_msg(self, message, is_error=False):
        from kivymd.uix.snackbar import MDSnackbar
        bg_color = (0.2, 0.6, 0.2, 1) if not is_error else (0.8, 0.2, 0.2, 1)
        MDSnackbar(
            MDLabel(
                text = message,
                font_style = "Subtitle1"
            ),
            md_bg_color=bg_color,
            y=dp(24),
            pos_hint={"center_x": 0.5},
            duration=3
        ).open()

    def show_text_dialog(self, title, text="", buttons=[]):
        self.txt_dialog = MDDialog(
            title=title,
            text=text,
            buttons=buttons
        )
        self.txt_dialog.open()

    def set_split_len(self, value):
        self.split_len = int(value)
        self.split_len_drp.text = str(self.split_len)
        self.split_len_options.dismiss()

    def open_img_file_manager(self):
        """Open the file manager to select an image file. On android use Downloads or Pictures folders only"""
        try:
            self.img_file_manager.show(self.external_storage)  # external storage
            self.is_img_manager_open = True
        except Exception as e:
            self.show_toast_msg(f"Error: {e}", is_error=True)

    def open_vid_file_manager(self, instance):
        """Open the file manager to select destination folder. On android use Downloads or Videos folders only"""
        try:
            self.vid_file_manager.show(self.external_storage)
            self.is_vid_manager_open = True
        except Exception as e:
            self.show_toast_msg(f"Error: {e}", is_error=True)

    def select_img_path(self, path: str):
        self.image_path = path
        api_resp = get_split_lens(path)
        split_lens = api_resp["split_lens"]
        image_details = api_resp["image_res"]
        img_box = self.root.ids.img_selector_lbl
        img_box.text = f"{image_details}"
        menu_items = [
            {
                "text": f"{option}",
                "on_release": lambda x=f"{option}": self.set_split_len(x),
                "font_size": sp(24)
            } for option in split_lens
        ]
        self.split_len_options = MDDropdownMenu(
            md_bg_color="#bdc6b0",
            caller=self.split_len_drp,
            items=menu_items,
        )
        if len(split_lens) >= 1:
            if 10 in split_lens:
                self.split_len = 10
            else:
                self.split_len = split_lens[0]
        else:
            self.split_len = 1
        self.split_len_drp.text = str(self.split_len)
        print(f"Initial split len: {self.split_len}")
        self.show_toast_msg(f"Selected image: {path}")
        self.img_file_exit_manager()

    def select_vid_path(self, path: str):
        """
        Called when a directory is selected. Save the Video file.
        """
        import shutil
        filename = os.path.basename(self.vid_download_path)
        chosen_path = os.path.join(path, filename) # destination path
        try:
            shutil.copyfile(self.vid_download_path, chosen_path)
            print(f"File successfully download to: {chosen_path}")
            self.show_toast_msg(f"File download to: {chosen_path}")
            self.vid_file_exit_manager()
            os.remove(self.vid_download_path)
            self.vid_download_path = ""
            player_box = self.root.ids.player_box
            player_box.clear_widgets()
        except Exception as e:
            print(f"Error saving file: {e}")
            self.show_toast_msg(f"Error saving file: {e}", is_error=True)

    def img_file_exit_manager(self, *args):
        """Called when the user reaches the root of the directory tree."""
        self.is_img_manager_open = False
        self.img_file_manager.close()

    def vid_file_exit_manager(self, *args):
        """Called when the user reaches the root of the directory tree."""
        self.is_vid_manager_open = False
        self.vid_file_manager.close()

    def submit_sketch_req(self):
        if self.image_path == "":
            self.show_toast_msg("No image is selected", is_error=True)
            return
        if self.is_cv2_running:
            self.show_toast_msg("Please wait for the previous request to finish", is_error=True)
            return
        split_len = self.split_len
        frame_rate = self.root.ids.frame_rate.text if self.root.ids.frame_rate.text != "" else self.frame_rate
        obj_skip_rate = self.root.ids.obj_skip_rate.text if self.root.ids.obj_skip_rate.text != "" else self.obj_skip_rate
        bck_skip_rate = self.root.ids.bck_skip_rate.text if self.root.ids.bck_skip_rate.text != "" else self.bck_skip_rate
        main_img_duration = self.root.ids.main_img_duration.text if self.root.ids.main_img_duration.text != "" else self.main_img_duration
        sketch_thread = Thread(target=initiate_sketch, args=(self.image_path, split_len, int(frame_rate), int(obj_skip_rate), int(bck_skip_rate), int(main_img_duration), self.task_complete_callback, self.video_dir, platform), daemon=True)
        sketch_thread.start()
        self.is_cv2_running = True
        player_box = self.root.ids.player_box
        player_box.clear_widgets()
        player_box.add_widget(MDSpinner(
            size_hint = [None, None],
            size = (dp(32), dp(32)),
            active = True,
            pos_hint={'center_x': .5, 'center_y': .5}
        ))

    def task_complete_callback(self, result):
        status = result["status"]
        player_box = self.root.ids.player_box
        message = result["message"]
        self.is_cv2_running = False
        if status is True:
            self.vid_download_path = message
            self.show_toast_msg(f"Video generated at: {message}")
            player_box.clear_widgets()
            player = VideoPlayer(
                source = message,
                options={'fit_mode': 'contain'}
            )
            down_btn = MDFloatingActionButton(
                icon="download",
                type="small",
                theme_icon_color="Custom",
                md_bg_color='#e9dff7',
                icon_color='#211c29',
            )
            player_box.add_widget(player)
            down_btn.bind(on_release=self.open_vid_file_manager)
            player_box.add_widget(down_btn)
            player.state = 'play'
        else:
            self.show_toast_msg(message, is_error=True)

    def reset_all(self):
        img_selector_lbl = self.root.ids.img_selector_lbl
        frame_rate = self.root.ids.frame_rate
        obj_skip_rate = self.root.ids.obj_skip_rate
        bck_skip_rate = self.root.ids.bck_skip_rate
        main_img_duration = self.root.ids.main_img_duration
        # start reset
        self.image_path = ""
        self.split_len = 10
        menu_items = []
        self.split_len_options = MDDropdownMenu(
            md_bg_color="#bdc6b0",
            caller=self.split_len_drp,
            items=menu_items,
        )
        self.split_len_drp.text = "speed"
        img_selector_lbl.text = "Select an image file >"
        frame_rate.text = "25"
        obj_skip_rate.text = "8"
        bck_skip_rate.text = "14"
        main_img_duration.text = "2"

    def events(self, instance, keyboard, keycode, text, modifiers):
        """Handle mobile device button presses (e.g., Android back button)."""
        if keyboard in (1001, 27):  # Android back button or equivalent
            if self.is_img_manager_open:
                # Check if we are at the root of the directory tree
                if self.img_file_manager.current_path == self.external_storage:
                    self.show_toast_msg(f"Closing file manager from main storage")
                    self.img_file_exit_manager()
                else:
                    self.img_file_manager.back()  # Navigate back within file manager
                return True  # Consume the event to prevent app exit
            if self.is_vid_manager_open:
                # Check if we are at the root of the directory tree
                if self.vid_file_manager.current_path == self.external_storage:
                    self.show_toast_msg(f"Closing file manager from main storage")
                    self.vid_file_exit_manager()
                else:
                    self.vid_file_manager.back()  # Navigate back within file manager
                return True  # Consume the event to prevent app exit
        return False

    def txt_dialog_closer(self, instance):
        self.txt_dialog.dismiss()

    def update_checker(self, instance):
        self.txt_dialog.dismiss()
        self.open_link("https://github.com/daslearning-org/image-to-animation-offline/releases")

    def open_demo_video(self):
        self.open_link("https://youtu.be/_UuAIjSzUJQ")

    def open_link(self, url):
        import webbrowser
        webbrowser.open(url)

if __name__ == '__main__':
    DlImg2SktchApp().run()
