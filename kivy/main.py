# python core modules
import os
os.environ['KIVY_GL_BACKEND'] = 'sdl2'
import sys
from threading import Thread
import queue

# kivy world
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.label import MDLabel
from kivymd.uix.button import MDFlatButton, MDFloatingActionButton, MDFillRoundFlatIconButton
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.spinner import MDSpinner
from kivymd.uix.filemanager import MDFileManager
from kivymd.uix.dialog import MDDialog
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.progressbar import MDProgressBar

from kivy.uix.videoplayer import VideoPlayer
from kivy.lang import Builder
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.utils import platform
from kivy.clock import Clock
from kivy.properties import StringProperty, NumericProperty, ObjectProperty
if platform == "android":
    from jnius import autoclass, PythonJavaClass, java_method

# IMPORTANT: Set this property for keyboard behavior
Window.softinput_mode = "below_target"

# Import your local screen classes & modules
from screens.divider import MyMDDivider
from sketchApi import get_split_lens, initiate_sketch

## Global definitions
__version__ = "0.3.0"
# Determine the base path for your application's resources
if getattr(sys, 'frozen', False):
    # Running as a PyInstaller bundle
    base_path = sys._MEIPASS
else:
    # Running in a normal Python environment
    base_path = os.path.dirname(os.path.abspath(__file__))
kv_file_path = os.path.join(base_path, 'main_layout.kv')

# custom kivymd/kivy classes
class TempSpinWait(MDBoxLayout):
    txt = StringProperty()

class VideoActionBtn(MDBoxLayout):
    pass

class BatchImgFolderBtn(MDFillRoundFlatIconButton):
    pass

class BatchStopBtn(MDBoxLayout):
    pass

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
    image_folder = StringProperty("")
    vid_download_path = StringProperty("")
    is_cv2_running = ObjectProperty()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Window.bind(on_keyboard=self.events)

    def build(self):
        self.theme_cls.primary_palette = "Blue"
        self.theme_cls.accent_palette = "Orange"
        self.batch_process = False
        self.end_color = True
        self.img_file_count = 0
        self.top_menu_items = {
            "Delete old sketches": {
                "icon": "delete",
                "action": "clear",
                "url": "",
            },
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
            },
            "Try Other Apps": {
                "icon": "google-play",
                "action": "web",
                "url": "https://daslearning.in/apps/",
            },
        }
        return Builder.load_file(kv_file_path)

    def on_start(self):
        file_m_height = 1
        # paths setup
        if platform == "android":
            file_m_height = 0.9 # to be implemented with ndk#28
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

            file_choose_grid = self.root.ids.file_choose_grid
            img_selector_lbl = self.root.ids.img_selector_lbl
            self.is_img_folder_open = False
            self.img_fold_manager = MDFileManager(
                exit_manager=self.img_fold_exit_manager,
                select_path=self.select_img_folder,
                selector="folder",  # Restrict to selecting directories only
            )
            fldr_btn = BatchImgFolderBtn()
            file_choose_grid.add_widget(fldr_btn)
            img_selector_lbl.text = "Select an image file or a folder with multiple images (batch) >"
        os.makedirs(self.video_dir, exist_ok=True)

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
        elif action == "clear":
            self.all_delete_alert()

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

    def open_img_fldr_manager(self):
        """Open the file manager to select an image file. On android use Downloads or Pictures folders only"""
        try:
            self.img_fold_manager.show(self.external_storage)  # external storage
            self.is_img_folder_open = True
        except Exception as e:
            self.show_toast_msg(f"Error: {e}", is_error=True)

    def open_vid_file_manager(self):
        """Open the file manager to select destination folder. On android use Downloads or Videos folders only"""
        try:
            self.vid_file_manager.show(self.external_storage)
            self.is_vid_manager_open = True
        except Exception as e:
            self.show_toast_msg(f"Error: {e}", is_error=True)

    def select_img_folder(self, path: str):
        self.img_fold_exit_manager()
        self.image_folder = path
        self.image_path = ""
        self.batch_process = True

        img_box = self.root.ids.img_selector_lbl
        img_box.text = f"Selected folder: {self.image_folder}"
        split_lens = [10, 20, 40] # only this are the feasible option in bulk select
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
        self.split_len = 10
        self.split_len_drp.text = str(self.split_len)
        print(f"Initial split len: {self.split_len}")

    def select_img_path(self, path: str):
        self.image_path = path
        self.image_folder = ""
        self.batch_process = False
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
        Called when a directory is selected. Save the Video file or zipped batch file.
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

    def img_fold_exit_manager(self, *args):
        """Called when the user reaches the root of the directory tree."""
        self.is_img_folder_open = False
        self.img_fold_manager.close()

    def current_delete_alert(self):
        filename = os.path.basename(self.vid_download_path)
        self.show_text_dialog(
            title="Delete this Video file?",
            text=f"To be deleted: {filename}. This action cannot be undone!",
            buttons=[
                MDFlatButton(
                    text="CANCEL",
                    theme_text_color="Custom",
                    text_color=self.theme_cls.primary_color,
                    on_release=self.txt_dialog_closer
                ),
                MDFlatButton(
                    text="DELETE",
                    theme_text_color="Custom",
                    text_color="red",
                    on_release=self.confirm_delete_video
                ),
            ],
        )

    def confirm_delete_video(self, instance):
        """
        Called when delete is confirmed.
        """
        self.txt_dialog_closer(instance)
        filename = os.path.basename(self.vid_download_path)
        if self.vid_download_path != "":
            try:
                os.remove(self.vid_download_path)
                self.vid_download_path = ""
                player_box = self.root.ids.player_box
                player_box.clear_widgets()
                self.show_toast_msg(f"{filename} has been deleted!")
            except Exception as e:
                print(f"Error saving file: {e}")
                self.show_toast_msg(f"Error deleting file: {e}", is_error=True)

    def set_end_img_color(self):
        btn_end_img = self.root.ids.btn_end_img
        if self.end_color:
            btn_end_img.icon = "toggle-switch-off"
            btn_end_img.icon_color = "white"
            btn_end_img.text_color = "white"
            btn_end_img.md_bg_color = "gray"
            self.end_color = False
        else:
            btn_end_img.icon = "toggle-switch"
            btn_end_img.icon_color = "magenta"
            btn_end_img.text_color = "black"
            btn_end_img.md_bg_color = "pink"
            self.end_color = True

    def submit_sketch_req(self):
        player_box = self.root.ids.player_box
        if self.batch_process:
            if self.image_folder == "":
                self.show_toast_msg("No folder is selected for batch process", is_error=True)
                return
            if self.is_cv2_running:
                self.show_toast_msg("Please wait for the previous request to finish", is_error=True)
                return
            self.batch_queue = queue.Queue()
            self.batch_op_files = []
            
            img_file_list = []
            img_extensions = [".png", ".jpg", ".jpeg", ".webp"]
            for file in os.listdir(self.image_folder):
                file_path_wo_ext, ext = os.path.splitext(file)
                if ext in img_extensions:
                    img_file_list.append(file)
                    self.img_file_count += 1
            print(f"Number of files in the batch: {self.img_file_count}")

            if self.img_file_count >= 1:
                #process batch
                player_box.clear_widgets()
                player_box.add_widget(TempSpinWait(txt = "Please wait while generating the sketch files (batch)..."))
                self.batch_progress = MDProgressBar(
                    value = 0,
                    pos_hint = {"center_x": .5, "center_y": .5},
                    size_hint_y = 0.2
                )
                player_box.add_widget(self.batch_progress)
                player_box.add_widget(BatchStopBtn())
                self.batch_queue.put("start")
                frame_rate = self.root.ids.frame_rate.text if self.root.ids.frame_rate.text != "" else self.frame_rate
                obj_skip_rate = self.root.ids.obj_skip_rate.text if self.root.ids.obj_skip_rate.text != "" else self.obj_skip_rate
                bck_skip_rate = self.root.ids.bck_skip_rate.text if self.root.ids.bck_skip_rate.text != "" else self.bck_skip_rate
                main_img_duration = self.root.ids.main_img_duration.text if self.root.ids.main_img_duration.text != "" else self.main_img_duration
                batch_thread = Thread(target=self.batch_loop, args=(img_file_list, int(frame_rate), int(obj_skip_rate), int(bck_skip_rate), int(main_img_duration)), daemon=True)
                batch_thread.start()
            else:
                self.show_toast_msg("There is no image file in the selected folder!", is_error=True)
                return
        else:
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
            sketch_thread = Thread(target=initiate_sketch, args=(self.image_path, split_len, int(frame_rate), int(obj_skip_rate), int(bck_skip_rate), int(main_img_duration), self.task_complete_callback, self.video_dir, platform, self.end_color), daemon=True)
            sketch_thread.start()
            self.is_cv2_running = True
            player_box.clear_widgets()
            player_box.add_widget(TempSpinWait(txt = "Please wait while generating the sketch..."))

    def batch_loop(self, img_file_list, frame_rate, obj_skip_rate, bck_skip_rate, main_img_duration):
        split_len = self.split_len
        progress_val = 0
        progress_steps = int(100/self.img_file_count)
        q_message = "start"
        for file in img_file_list:
            full_img_path = os.path.join(self.image_folder, file)
            sketch_thread = Thread(target=initiate_sketch, args=(full_img_path, split_len, int(frame_rate), int(obj_skip_rate), int(bck_skip_rate), int(main_img_duration), self.task_complete_callback, self.video_dir, platform, self.end_color), daemon=True)
            sketch_thread.start()

            self.is_cv2_running = True
            self.batch_queue.put("start")
            while self.img_file_count >= 1:
                try:
                    q_message = self.batch_queue.get(timeout=1)
                    if q_message == "wait":
                        # no action needed, need to wait for the current conversion
                        continue
                    elif q_message == "next":
                        # break the process
                        self.is_cv2_running = False
                        progress_val += progress_steps
                        Clock.schedule_once(lambda dt: self.batch_prog_updater(progress_val))
                        break
                    elif q_message == "stop":
                        break
                    else:
                        continue
                except:
                    # queue empty
                    continue
            self.img_file_count -= 1
            if q_message == "stop":
                #stop processing next files
                break
        print("Finished all files")
        Clock.schedule_once(lambda dt: self.batch_end_trigger())

    def stop_batch(self):
        if self.batch_process:
            self.batch_queue.put("stop")

    def task_complete_callback(self, result):
        player_box = self.root.ids.player_box
        status = result["status"]
        message = result["message"]
        self.is_cv2_running = False
        if status is True:
            if self.batch_process:
                self.batch_queue.put("next")
                self.batch_op_files.append(message)
            else:
                self.vid_download_path = message
                self.show_toast_msg(f"Video generated at: {message}")
                player_box.clear_widgets()
                player = VideoPlayer(
                    source = message,
                    options={'fit_mode': 'contain'}
                )
                down_btn = VideoActionBtn()
                player_box.add_widget(player)
                player_box.add_widget(down_btn)
                player.state = 'play'
        else:
            self.show_toast_msg(message, is_error=True)
            if self.batch_process:
                self.batch_queue.put("next")

    def batch_end_trigger(self):
        # All completed triggered
        player_box = self.root.ids.player_box
        player_box.clear_widgets()
        self.batch_progress.value = 100
        if len(self.batch_op_files) >= 1:
            import datetime
            now = datetime.datetime.now()
            current_time = str(now.strftime("%H%M%S"))
            current_date = str(now.strftime("%Y%m%d"))
            folder_zip = f"bat_{current_date}_{current_time}.zip"
            folder_zip_full = os.path.join(self.video_dir, folder_zip) 
            from zipfile import ZipFile
            with ZipFile(folder_zip_full, "w") as zip_obj:
                for file in self.batch_op_files:
                    zip_obj.write(file, os.path.basename(file))
                    os.remove(file)
            self.show_toast_msg(f"Batch process complete & output file is: {folder_zip_full}")
            player_box.add_widget(MDLabel(text=f"Batch process complete & output file is: {folder_zip_full}"))
            self.vid_download_path = folder_zip_full
            down_btn = VideoActionBtn()
            player_box.add_widget(down_btn)
        else:
            self.show_toast_msg("No video files were generated in the batch!", is_error=True)

    def batch_prog_updater(self, progress_val):
        self.batch_progress.value = progress_val

    def reset_all(self):
        img_selector_lbl = self.root.ids.img_selector_lbl
        frame_rate = self.root.ids.frame_rate
        obj_skip_rate = self.root.ids.obj_skip_rate
        bck_skip_rate = self.root.ids.bck_skip_rate
        main_img_duration = self.root.ids.main_img_duration
        # start reset
        self.image_path = ""
        self.image_folder = ""
        self.split_len = 10
        menu_items = []
        self.split_len_options = MDDropdownMenu(
            md_bg_color="#bdc6b0",
            caller=self.split_len_drp,
            items=menu_items,
        )
        self.split_len_drp.text = "speed"
        if platform == "android":
            img_selector_lbl.text = "Use the button to select an image >"
        else:
            img_selector_lbl.text = "Select an image file or a folder with multiple images (batch) >"
        frame_rate.text = "25"
        obj_skip_rate.text = "8"
        bck_skip_rate.text = "14"
        main_img_duration.text = "2"
        player_box = self.root.ids.player_box
        player_box.clear_widgets()
        btn_end_img = self.root.ids.btn_end_img
        btn_end_img.icon = "toggle-switch"
        btn_end_img.icon_color = "magenta"
        btn_end_img.text_color = "black"
        btn_end_img.md_bg_color = "pink"
        self.end_color = True

    def all_delete_alert(self):
        del_vid_count = 0
        for filename in os.listdir(self.video_dir):
            if filename.endswith(".mp4") or filename.endswith(".avi") or filename.endswith(".zip"):
                del_vid_count += 1
        self.show_text_dialog(
            title="Delete all Sketch videos?",
            text=f"There are total: {del_vid_count} files. This action cannot be undone!",
            buttons=[
                MDFlatButton(
                    text="CANCEL",
                    theme_text_color="Custom",
                    text_color=self.theme_cls.primary_color,
                    on_release=self.txt_dialog_closer
                ),
                MDFlatButton(
                    text="DELETE",
                    theme_text_color="Custom",
                    text_color="red",
                    on_release=self.delete_action
                ),
            ],
        )

    def delete_action(self, instance):
        # Custom function called when DISCARD is clicked
        for filename in os.listdir(self.video_dir):
            if filename.endswith(".mp4") or filename.endswith(".avi") or filename.endswith(".zip"):
                file_path = os.path.join(self.video_dir, filename)
                try:
                    os.unlink(file_path)
                    print(f"Deleted {file_path}")
                except Exception as e:
                    print(f"Could not delete the audion files, error: {e}")
        self.show_toast_msg("Executed the video file cleanup!")
        self.txt_dialog_closer(instance)
        player_box = self.root.ids.player_box
        player_box.clear_widgets()

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
