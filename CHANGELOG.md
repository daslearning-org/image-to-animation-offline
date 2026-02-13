# Changes on the App

## App Details
- APK for `Android`, EXE for `Windows` & the other file without any extension is for `Linux`. [Documentation Link](https://blog.daslearning.in/llm_ai/genai/image-to-animation.html)

## Change Details

### 0.4.0
- Using [Kivy-Plyer](https://github.com/kivy/plyer/blob/master/plyer/facades/filechooser.py) to use native file manager. This will also remember the last selected path (if we have done any upload after launching the app, not applicable for Android).

### 0.3.1
- Setting a dafault `speed` (split let) based on image resolution.
- Adding progress bar during the sketch job.

### 0.3.0

#### All versions
- Added a delete button along with download button after sketch generation.
- Dedicated cleanup button in the menu bar.
- Added a link for `Other Open-Source Apps` from us.
- A waiting message with spinner instead of just a spinner while generating skecth.
- A button to choose if we want the original image or the grayscale image to be shown as end image of the sketch video.

#### Desktop only changes:
- You can now select a folder & all images will be used to create multiple sketch videos (batch process).

### 0.2.2
- Now we can select image from android phone memory's DCIM, Downloads or Pictures (sub-folder under this also works fine).
- All logics remain same, so no change on desktop apps.

### 0.2.1
- Adding ffmpeg convert step after the animation generation which reduces the video file size

### 0.1.1
- Fixing the color changing (was becomin blue) of final image.
- Trying to keep the aspect ratio as close as possible to avoid stubbed ot streched effect.

### 0.1.0
- Added relevant links in the app

### 0.0.14
- Releasing the initial working version of the app
