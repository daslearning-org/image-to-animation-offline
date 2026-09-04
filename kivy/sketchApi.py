import os, stat, shutil
import sys
import subprocess
from pathlib import Path
import time
import math
import json
import datetime
import cv2
import numpy as np
from kivy.clock import Clock

# global variables
if getattr(sys, 'frozen', False):
    # Running as a PyInstaller bundle
    base_path = sys._MEIPASS
else:
    # Running in a normal Python environment
    base_path = os.path.dirname(os.path.abspath(__file__))
images_path = os.path.join(base_path, 'data', 'images')
hand_path = os.path.join(images_path, 'drawing-hand.png')
hand_mask_path = os.path.join(images_path, 'hand-mask.png')
save_path = os.path.join(base_path, "save_videos")
platform = "linux"
progress_updater = None

## All functions
def euc_dist(arr1, point):
    square_sub = (arr1 - point) ** 2
    return np.sqrt(np.sum(square_sub, axis=1))

def preprocess_image(img, variables):
    #img = cv2.imread(img_path)
    img_ht, img_wd = img.shape[0], img.shape[1]
    img = cv2.resize(img, (variables.resize_wd, variables.resize_ht))
    img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # color histogram equilization
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(3, 3))
    cl1 = clahe.apply(img_gray)

    # gaussian adaptive thresholding
    img_thresh = cv2.adaptiveThreshold(
        img_gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 10
    )

    # adding all the computed required items in variables object
    variables.img_ht = img_ht
    variables.img_wd = img_wd
    variables.img_gray = img_gray
    variables.img_thresh = img_thresh
    variables.img = img
    return variables


def preprocess_hand_image(hand_path, hand_mask_path, variables):
    hand = cv2.imread(hand_path)
    hand_mask = cv2.imread(hand_mask_path, cv2.IMREAD_GRAYSCALE)

    top_left, bottom_right = get_extreme_coordinates(hand_mask)
    hand = hand[top_left[1] : bottom_right[1], top_left[0] : bottom_right[0]]
    hand_mask = hand_mask[top_left[1] : bottom_right[1], top_left[0] : bottom_right[0]]
    hand_mask_inv = 255 - hand_mask

    # standardizing the hand masks
    hand_mask = hand_mask / 255
    hand_mask_inv = hand_mask_inv / 255

    # making the hand background black
    hand_bg_ind = np.where(hand_mask == 0)
    hand[hand_bg_ind] = [0, 0, 0]

    # getting the img and hand dim
    hand_ht, hand_wd = hand.shape[0], hand.shape[1]

    variables.hand_ht = hand_ht
    variables.hand_wd = hand_wd
    variables.hand = hand
    variables.hand_mask = hand_mask
    variables.hand_mask_inv = hand_mask_inv
    return variables


def get_extreme_coordinates(mask):
    indices = np.where(mask == 255)
    # Extract the x and y coordinates of the pixels.
    x = indices[1]
    y = indices[0]

    # Find the minimum and maximum x and y coordinates.
    topleft = (np.min(x), np.min(y))
    bottomright = (np.max(x), np.max(y))

    return topleft, bottomright


def flash_element_color(variables, element_mask, duration_sec=0.3):
    """
    Flash the full color of an element instantly (no animation).
    Used in Element Mode + End Colour to show element color after drawing edges.
    
    Args:
        variables: AllVariables object
        element_mask: Binary mask for the element (255=element, 0=background)
        duration_sec: How long to display the color (default: 0.3 seconds)
    """
    frames = int(variables.frame_rate * duration_sec)
    
    for _ in range(frames):
        # Copy current frame and apply element color from original image
        temp_frame = variables.drawn_frame.copy()
        temp_frame[element_mask == 255] = variables.img[element_mask == 255]
        variables.video_object.write(temp_frame)
    
    # Update drawn_frame to include this element's color
    variables.drawn_frame[element_mask == 255] = variables.img[element_mask == 255]


def detect_elements(img, white_gap_threshold=10, sort_direction="right-top"):
    """
    Detect separate elements on white background based on white gap between them.
    
    Args:
        img: BGR image (already resized)
        white_gap_threshold: Minimum white pixels gap between elements (larger = merge closer elements)
        sort_direction: One of "right-top", "right-bottom", "left-top", "left-bottom"
    
    Returns:
        List of element masks (each mask is same size as image, 255=element area)
    """
    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Threshold to find non-white pixels (elements)
    # Pixels below 240 are considered non-white (elements)
    _, binary = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
    
    # Apply morphological dilation to merge elements that are close together
    # The kernel size is based on white_gap_threshold
    if white_gap_threshold > 0:
        kernel = np.ones((white_gap_threshold, white_gap_threshold), np.uint8)
        dilated = cv2.dilate(binary, kernel, iterations=1)
    else:
        dilated = binary
    
    # Find connected components
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(dilated, connectivity=8)
    
    # Extract element information (skip label 0 which is background)
    elements = []
    for i in range(1, num_labels):
        # Get bounding box
        x = stats[i, cv2.CC_STAT_LEFT]
        y = stats[i, cv2.CC_STAT_TOP]
        w = stats[i, cv2.CC_STAT_WIDTH]
        h = stats[i, cv2.CC_STAT_HEIGHT]
        area = stats[i, cv2.CC_STAT_AREA]

        # Get centroid for sorting
        cx, cy = centroids[i]

        # Create mask for this element using ORIGINAL binary (not dilated)
        element_mask = np.zeros_like(binary)
        element_mask[labels == i] = 255

        # Erode back to original size (reverse the dilation)
        if white_gap_threshold > 0:
            element_mask = cv2.erode(element_mask, kernel, iterations=1)

        # Apply to original binary to get exact element pixels
        element_mask = cv2.bitwise_and(binary, element_mask)
        
        elements.append({
            'mask': element_mask,
            'x': x,
            'y': y,
            'w': w,
            'h': h,
            'cx': cx,
            'cy': cy,
            'area': area
        })

    # Sort elements based on sort_direction
    if sort_direction == "right-top":
        # Rightmost first (larger x), then topmost (smaller y)
        elements.sort(key=lambda e: (-e['cx'], e['cy']))
    elif sort_direction == "right-bottom":
        # Rightmost first (larger x), then bottommost (larger y)
        elements.sort(key=lambda e: (-e['cx'], -e['cy']))
    elif sort_direction == "left-top":
        # Leftmost first (smaller x), then topmost (smaller y)
        elements.sort(key=lambda e: (e['cx'], e['cy']))
    elif sort_direction == "left-bottom":
        # Leftmost first (smaller x), then bottommost (larger y)
        elements.sort(key=lambda e: (e['cx'], -e['cy']))

    # Return list of masks
    element_masks = [e['mask'] for e in elements]
    print(f"Detected {len(element_masks)} elements with white gap threshold: {white_gap_threshold}px")
    return element_masks

def draw_hand_on_img(
    drawing,
    hand,
    drawing_coord_x,
    drawing_coord_y,
    hand_mask_inv,
    hand_ht,
    hand_wd,
    img_ht,
    img_wd,
):
    remaining_ht = img_ht - drawing_coord_y
    remaining_wd = img_wd - drawing_coord_x
    if remaining_ht > hand_ht:
        crop_hand_ht = hand_ht
    else:
        crop_hand_ht = remaining_ht

    if remaining_wd > hand_wd:
        crop_hand_wd = hand_wd
    else:
        crop_hand_wd = remaining_wd

    hand_cropped = hand[:crop_hand_ht, :crop_hand_wd]
    hand_mask_inv_cropped = hand_mask_inv[:crop_hand_ht, :crop_hand_wd]

    drawing[
        drawing_coord_y : drawing_coord_y + crop_hand_ht,
        drawing_coord_x : drawing_coord_x + crop_hand_wd,
    ][:, :, 0] = (
        drawing[
            drawing_coord_y : drawing_coord_y + crop_hand_ht,
            drawing_coord_x : drawing_coord_x + crop_hand_wd,
        ][:, :, 0]
        * hand_mask_inv_cropped
    )
    drawing[
        drawing_coord_y : drawing_coord_y + crop_hand_ht,
        drawing_coord_x : drawing_coord_x + crop_hand_wd,
    ][:, :, 1] = (
        drawing[
            drawing_coord_y : drawing_coord_y + crop_hand_ht,
            drawing_coord_x : drawing_coord_x + crop_hand_wd,
        ][:, :, 1]
        * hand_mask_inv_cropped
    )
    drawing[
        drawing_coord_y : drawing_coord_y + crop_hand_ht,
        drawing_coord_x : drawing_coord_x + crop_hand_wd,
    ][:, :, 2] = (
        drawing[
            drawing_coord_y : drawing_coord_y + crop_hand_ht,
            drawing_coord_x : drawing_coord_x + crop_hand_wd,
        ][:, :, 2]
        * hand_mask_inv_cropped
    )

    drawing[
        drawing_coord_y : drawing_coord_y + crop_hand_ht,
        drawing_coord_x : drawing_coord_x + crop_hand_wd,
    ] = (
        drawing[
            drawing_coord_y : drawing_coord_y + crop_hand_ht,
            drawing_coord_x : drawing_coord_x + crop_hand_wd,
        ]
        + hand_cropped
    )
    return drawing


def draw_masked_object(
    variables, object_mask=None, skip_rate=5, black_pixel_threshold=10, progress_callback=None
):
    """
    skip_rate is not provided via variables because this function does not
    know it is drawing object or background or an entire image
    """
    # --- Layered Detection Logic ---
    n_cuts_vertical = int(math.ceil(variables.resize_ht / variables.split_len))
    n_cuts_horizontal = int(math.ceil(variables.resize_wd / variables.split_len))

    # 1. Detect Line Blocks (Structural details)
    line_mask = variables.img_thresh.copy()
    if object_mask is not None:
        line_mask[object_mask == 0] = 255
    
    grid_of_lines = np.array(np.split(line_mask, n_cuts_horizontal, axis=-1))
    grid_of_lines = np.array(np.split(grid_of_lines, n_cuts_vertical, axis=-2))
    
    has_line = (grid_of_lines < black_pixel_threshold) * 1
    has_line = np.sum(np.sum(has_line, axis=-1), axis=-1)
    line_indices = np.array(np.where(has_line > 0)).T

    work_stages = []
    if variables.draw_color:
        # 2. Detect Color Blocks (Backgrounds/Fills)
        img_full_sum = np.sum(variables.img.astype(np.uint32), axis=-1)
        color_mask = np.zeros_like(variables.img_thresh)
        color_mask[img_full_sum < 750] = 0
        color_mask[img_full_sum >= 750] = 255
        if object_mask is not None:
            color_mask[object_mask == 0] = 255
            
        grid_of_colors = np.array(np.split(color_mask, n_cuts_horizontal, axis=-1))
        grid_of_colors = np.array(np.split(grid_of_colors, n_cuts_vertical, axis=-2))
        
        has_color = (grid_of_colors < black_pixel_threshold) * 1
        has_color = np.sum(np.sum(has_color, axis=-1), axis=-1)
        color_indices = np.array(np.where(has_color > 0)).T
        
        # Separate into unique stages: Outlines first, then Fills
        line_set = set(map(tuple, line_indices))
        fill_indices = np.array([idx for idx in color_indices if tuple(idx) not in line_set])
        
        work_stages = [line_indices, fill_indices]
    else:
        # Grayscale mode: only lines
        work_stages = [line_indices]

    counter = 0
    selected_ind_val = np.array([0, 0]) # Tracking last position for continuity between stages
    
    # Progress tracking
    total_pixels_to_draw = sum(len(stage) for stage in work_stages)
    pixels_drawn = 0

    # Phase 2 (fills) is faster than phase 1 (outlines)
    for stage_idx, cut_black_indices in enumerate(work_stages):
        if len(cut_black_indices) == 0:
            continue
            
        # Stage-specific speed adjustment: Phase 2 (fills) is faster than phase 1 (outlines)
        if variables.draw_color and stage_idx == 1:
            effective_skip_rate = skip_rate * variables.fill_speed_multiplier
        else:
            effective_skip_rate = skip_rate

        # For the first block of any stage, find the closest to the last known position
        euc_arr = euc_dist(cut_black_indices, selected_ind_val)
        selected_ind = np.argmin(euc_arr)

        while len(cut_black_indices) > 0:
            selected_ind_val = cut_black_indices[selected_ind].copy()
            range_v_start = selected_ind_val[0] * variables.split_len
            range_v_end = range_v_start + variables.split_len
            range_h_start = selected_ind_val[1] * variables.split_len
            range_h_end = range_h_start + variables.split_len
            if variables.draw_color:
                temp_drawing = variables.img[range_v_start:range_v_end, range_h_start:range_h_end].copy()
                # Full coloring: revealed block is shown exactly as is from the original image
            else:
                temp_drawing = np.zeros((variables.split_len, variables.split_len, 3))
                temp_drawing[:, :, 0] = grid_of_lines[selected_ind_val[0]][selected_ind_val[1]]
                temp_drawing[:, :, 1] = grid_of_lines[selected_ind_val[0]][selected_ind_val[1]]
                temp_drawing[:, :, 2] = grid_of_lines[selected_ind_val[0]][selected_ind_val[1]]

            variables.drawn_frame[range_v_start:range_v_end, range_h_start:range_h_end] = (
                temp_drawing
            )

            if variables.draw_hand:
                hand_coord_x = range_h_start + int(variables.split_len / 2)
                hand_coord_y = range_v_start + int(variables.split_len / 2)
                drawn_frame_with_hand = draw_hand_on_img(
                    variables.drawn_frame.copy(),
                    variables.hand.copy(),
                    hand_coord_x,
                    hand_coord_y,
                    variables.hand_mask_inv.copy(),
                    variables.hand_ht,
                    variables.hand_wd,
                    variables.resize_ht,
                    variables.resize_wd,
                )
            else:
                drawn_frame_with_hand = variables.drawn_frame.copy()

            # delete the selected ind from the d_array
            cut_black_indices[selected_ind] = cut_black_indices[-1]
            cut_black_indices = cut_black_indices[:-1]

            if len(cut_black_indices) == 0:
                break
                
            # select the next new index
            euc_arr = euc_dist(cut_black_indices, selected_ind_val)
            selected_ind = np.argmin(euc_arr)

            counter += 1
            if counter % effective_skip_rate == 0:
                variables.video_object.write(drawn_frame_with_hand)

            if counter % 40 == 0 and platform != "android":
                print("len of black indices: ", len(cut_black_indices))

            # Report progress
            if progress_updater:
                pixels_drawn += 1
                if pixels_drawn % 20 == 0 or pixels_drawn == total_pixels_to_draw:
                    progress_val = int((pixels_drawn / total_pixels_to_draw) * 100)
                    Clock.schedule_once(lambda dt: progress_updater(progress_val))

def draw_whiteboard_animations(
    img, mask_path, hand_path, hand_mask_path, save_video_path, variables, end_color=True
):
    if mask_path is not None:
        object_mask_exists = True
    else:
        object_mask_exists = False

    # reading the image and converting it to grayscale,
    # computing clahe and later therholding
    variables = preprocess_image(img=img, variables=variables)

    # reading hand image and preprocess
    variables = preprocess_hand_image(
        hand_path=hand_path, hand_mask_path=hand_mask_path, variables=variables
    )

    # calculate how much time it takes to make video for 1 image
    start_time = time.time()

    # defining the video object
    print(f"Selected platform in sketch api: {platform}")
    if platform == "android":
        fourcc = cv2.VideoWriter_fourcc(*"MJPG") #mpg2 or h264 or MJPG
    else:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v") #mp4v
    variables.video_object = cv2.VideoWriter(
        save_video_path,
        fourcc,
        variables.frame_rate,
        (variables.resize_wd, variables.resize_ht),
    )

    # creating an emtpy frame and select 0th index as the starting point to draw
    variables.drawn_frame = np.zeros(variables.img.shape, np.uint8) + np.array(
        [255, 255, 255], np.uint8
    )

    if object_mask_exists:

        # reading the object masks
        with open(mask_path) as file:
            object_masks = json.load(file)

        background_mask = (
            np.zeros((variables.resize_ht, variables.resize_wd), dtype=np.uint8) + 255
        )

        for object in object_masks["shapes"]:
            # Create an empty mask array
            object_mask = np.zeros((variables.img_ht, variables.img_wd), dtype=np.uint8)

            # Get the object points as a list of tuples
            object_points = np.array(object["points"], dtype=np.int32)
            object_points = np.expand_dims(object_points, axis=0)

            # Fill the polygon with white color (255) on the mask array using cv2
            cv2.fillPoly(object_mask, object_points, 255)

            # resizing the object_mask
            object_mask = cv2.resize(
                object_mask, (variables.resize_wd, variables.resize_ht)
            )

            # get the object and its background indices
            object_ind = np.where(object_mask == 255)

            # remove the object from backgrond mask
            background_mask[object_ind] = 0

            # create animation for the selected object
            draw_masked_object(
                variables=variables,
                object_mask=object_mask,
                skip_rate=variables.object_skip_rate,
            )

        # now draw the last remaing background part
        """
        # update the split len for background part by which the 
        # area covered in one loop iteration will be much larger
        """
        # Optional:
        print("Drawing the blakground region..")
        variables.split_len = 20
        draw_masked_object(
            variables=variables,
            object_mask=background_mask,
            skip_rate=variables.bg_object_skip_rate,
        )
    elif variables.element_mode:
        # Element-by-element mode: detect separate elements and draw each completely
        print("Element Mode: Detecting separate elements...")
        element_masks = detect_elements(
            variables.img,
            variables.white_gap_threshold,
            variables.element_sort_direction
        )
        
        if len(element_masks) == 0:
            print("No elements detected! Drawing entire image normally...")
            draw_masked_object(
                variables=variables,
                skip_rate=variables.object_skip_rate,
            )
        else:
            # Draw each element completely before moving to the next
            for idx, element_mask in enumerate(element_masks, 1):
                print(f"Drawing element {idx}/{len(element_masks)}...")
                
                if variables.two_pass:
                    # Two Pass mode for this element
                    print(f"  Pass 1: Drawing edges (element {idx})...")
                    original_draw_color = variables.draw_color
                    variables.draw_color = False
                    draw_masked_object(
                        variables=variables,
                        object_mask=element_mask,
                        skip_rate=variables.object_skip_rate,
                    )
                    
                    print(f"  Pass 2: Filling color (element {idx})...")
                    variables.draw_color = True
                    # Make the color pass slightly faster
                    original_skip_rate = variables.object_skip_rate
                    variables.object_skip_rate = int(original_skip_rate * 1.5)
                    
                    draw_masked_object(
                        variables=variables,
                        object_mask=element_mask,
                        skip_rate=variables.object_skip_rate,
                    )
                    
                    # Restore original values
                    variables.object_skip_rate = original_skip_rate
                    variables.draw_color = original_draw_color
                    
                elif variables.end_color and not variables.draw_color:
                    # End Colour mode: draw edges then flash color
                    print(f"  Drawing edges (element {idx})...")
                    draw_masked_object(
                        variables=variables,
                        object_mask=element_mask,
                        skip_rate=variables.object_skip_rate,
                    )
                    
                    print(f"  Flashing color (element {idx})...")
                    flash_element_color(variables, element_mask, duration_sec=0.3)
                    
                else:
                    # Normal draw (with or without color)
                    draw_masked_object(
                        variables=variables,
                        object_mask=element_mask,
                        skip_rate=variables.object_skip_rate,
                    )
    else:
        # variables.split_len = 15
        # variables.object_skip_rate = 8
        # draw the entire image without any mask
        
        if variables.two_pass:
            print("Running First Pass: Lines...")
            variables.draw_color = False
            draw_masked_object(
                variables=variables,
                skip_rate=variables.object_skip_rate,
            )
            
            print("Running Second Pass: Color...")
            variables.draw_color = True
            # Make the color pass slightly faster by increasing skip rate by ~1.5x
            original_skip_rate = variables.object_skip_rate
            variables.object_skip_rate = int(original_skip_rate * 1.5)
            
            draw_masked_object(
                variables=variables,
                skip_rate=variables.object_skip_rate,
            )
            # Restore original skip rate
            variables.object_skip_rate = original_skip_rate
        else:
            draw_masked_object(
                variables=variables,
                skip_rate=variables.object_skip_rate,
            )

    # Final "Cleanup" Reveal: ensures the full image is perfectly displayed before the static end frames
    if end_color:
        end_img = variables.img
    else:
        end_img = cv2.cvtColor(variables.img_thresh, cv2.COLOR_GRAY2BGR)

    variables.drawn_frame[:, :, :] = end_img

    # User can select if they want a colour image or grayscale image shown at the end
    # (The end_img selection logic was already here, sticking to the single finalization)
    # Ending the video with original original image
    for i in range(variables.frame_rate * variables.end_gray_img_duration_in_sec):
        #variables.video_object.write(variables.img)
        variables.video_object.write(end_img)

    # Calculating the total execution time
    end_time = time.time()
    print("total time: ", end_time - start_time)

    # closing the video object
    variables.video_object.release()

def find_nearest_res(given):
    arr = np.array([640, 360, 480, 1280, 720, 1920, 1080, 2560, 1440, 3840, 2160, 7680, 4320])
    idx = (np.abs(arr - given)).argmin()  # Find index of minimum difference
    return arr[idx]

def resize_with_padding(img, target_width, target_height, color=(255,255,255)):
    """
    Resize image to target resolution keeping aspect ratio.
    Remaining area is padded with given color (default white).
    """

    h, w = img.shape[:2]
    # scale ratio (keep aspect ratio)
    scale = min(target_width / w, target_height / h)
    # new size
    new_w = int(w * scale)
    new_h = int(h * scale)
    # resize image
    resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
    # compute padding
    pad_w = target_width - new_w
    pad_h = target_height - new_h
    top = pad_h // 2
    bottom = pad_h - top
    left = pad_w // 2
    right = pad_w - left

    # add border (padding)
    padded = cv2.copyMakeBorder(
        resized,
        top, bottom, left, right,
        cv2.BORDER_CONSTANT,
        value=color
    )
    return padded


class AllVariables:
    def __init__(
        self,
        frame_rate=None,
        resize_wd=None,
        resize_ht=None,
        split_len=None,
        object_skip_rate=None,
        bg_object_skip_rate=None,
        end_gray_img_duration_in_sec=None,
        draw_hand=True,
        draw_color=True,
        two_pass=False,
        fill_speed_multiplier=5,
        element_mode=False,
        white_gap_threshold=10,
        element_sort_direction="right-top",
        end_color=True,
    ):
        self.frame_rate = frame_rate
        self.resize_wd = resize_wd
        self.resize_ht = resize_ht
        self.split_len = split_len
        self.object_skip_rate = object_skip_rate
        self.bg_object_skip_rate = bg_object_skip_rate
        self.end_gray_img_duration_in_sec = end_gray_img_duration_in_sec
        self.draw_hand = draw_hand
        self.draw_color = draw_color
        self.two_pass = draw_color
        self.fill_speed_multiplier = fill_speed_multiplier
        self.element_mode = element_mode
        self.white_gap_threshold = white_gap_threshold
        self.element_sort_direction = element_sort_direction
        self.end_color = end_color

def common_divisors(num1, num2):
    """
    Finds all common divisors of two numbers, stores them in a list,
    and returns the list sorted in ascending order.
    """
    divisors1 = []
    divisors2 = []
    common_divs = []

    # Find divisors of num1
    for i in range(1, num1 + 1):
        if num1 % i == 0:
            divisors1.append(i)

    # Find divisors of num2
    for i in range(1, num2 + 1):
        if num2 % i == 0:
            divisors2.append(i)

    # Find common divisors
    for divisor in divisors1:
        if divisor in divisors2:
            common_divs.append(divisor)

    common_divs.sort()  # Sort the list in ascending order
    return common_divs


def ffmpeg_convert(source_vid, dest_vid, platform="linux"):
    ff_stat = False
    try:
        import av
        # ---> diagnostic code
        print("PyAV: ", av.__version__)
        #print("FFmpeg: ", av.library_versions)
        #for codec in sorted(av.codec.codecs_available):
        #    if "264" in codec.lower():
        #        print(codec)
        # <--- diag end

        src_path = Path(source_vid)
        input_container = av.open(src_path, mode="r")
        output_container = av.open(dest_vid, mode="w")
        
        in_stream = input_container.streams.video[0]
        width = in_stream.codec_context.width
        height = in_stream.codec_context.height
        fps = in_stream.average_rate
        # set output params
        if platform == "android":
            out_stream = output_container.add_stream("libx264", rate=fps)
        else:
            out_stream = output_container.add_stream("h264", rate=fps)
        out_stream.width = width
        out_stream.height = height
        out_stream.pix_fmt = "yuv420p"
        # Better quality control
        out_stream.options = {
            "crf": "20"  # adjust between 18–23, not working on android with v17
            #"bitrate": "2000000"
        }
        # ---> diagnostic code
        #print("Format: ", input_container.format.name)
        #for s in input_container.streams:
        #    print("Stream: ", s.type, s.codec_context.name)
        #print("Selected codec: ", out_stream.codec_context.codec.name)
        # <--- diag end
        for frame in input_container.decode(video=0):
            packet = out_stream.encode(frame)
            if packet:
                output_container.mux(packet)
        packet = out_stream.encode(None)
        if packet:
            output_container.mux(packet)
        output_container.close()
        input_container.close()

        print(f"ffmpeg convert success, converted file: {dest_vid}")
        ff_stat = True
    except Exception as e:
        print(f"ffmpeg convert error: {e}")
    return ff_stat

def initiate_sketch(
        image_path, split_len, frame_rate, object_skip_rate, bg_object_skip_rate, main_img_duration, callback, save_path=save_path,
        which_platform="linux", end_color=True, draw_hand=True, max_1080p=True,
        progress_callback=None ):
    global platform
    platform = which_platform
    final_result = {"status": False, "message": "Initial load"}
    try:
        image_bgr = cv2.imread(image_path)
        mask_path = None # To be added later
        # video save path
        now = datetime.datetime.now()
        current_time = str(now.strftime("%H%M%S"))
        current_date = str(now.strftime("%Y%m%d"))
        if platform == "android":
            video_save_name = f"vid_{current_date}_{current_time}.avi" #mpg
        else:
            video_save_name = f"vid_{current_date}_{current_time}.mp4" #mp4
        save_video_path = os.path.join(save_path, video_save_name)
        ffmpeg_file_name = f"vid_{current_date}_{current_time}_h264.mp4"
        ffmpeg_video_path = os.path.join(save_path, ffmpeg_file_name)
        os.makedirs(os.path.dirname(save_video_path), exist_ok=True)
        print("save_video_path: ", save_video_path)

        # Get image width & height. If the resolution is not standard & split length is not a common divisor, get the nearest standard res
        img_ht, img_wd = image_bgr.shape[0], image_bgr.shape[1]
        if max_1080p and (img_ht > 1920 or img_wd > 1920):
            if img_wd > img_ht: # 16:9
                img_wd = 1920
                img_ht = 1080
            else: # 9:16
                img_ht = 1920
                img_wd = 1080
            image_bgr = resize_with_padding(
                img=image_bgr,
                target_width=img_wd,
                target_height=img_ht
            )
        else:
            aspect_ratio = img_wd / img_ht
            img_ht = find_nearest_res(img_ht)
            new_aspect_wd = int(img_ht * aspect_ratio)
            img_wd = find_nearest_res(new_aspect_wd)
        print(f"Target width: {img_wd} x height: {img_ht}")

        # constants and variables object
        variables = AllVariables(
            frame_rate = frame_rate,  # frame rate for the output video
            resize_wd = img_wd,  # output video width
            resize_ht = img_ht,  # output video height
            split_len = split_len,  # the image is devided into grids. When split_len = 10, the image is devided as: img_ht/10, img_wd/10
            object_skip_rate = object_skip_rate,  # when drawing, 8 pixels colored will be saved together in the video
            # increase this number to make the video runtime smaller (draws faster)
            bg_object_skip_rate = bg_object_skip_rate,  # assuming background region is larger, hence increasing the skip rate
            end_gray_img_duration_in_sec = main_img_duration,  # the last few secs of the video, for every image will have the entire original image shown as is
            draw_hand=draw_hand,
        )

        # invoking the drawing function
        global progress_updater
        progress_updater = progress_callback
        try:
            draw_whiteboard_animations(
                image_bgr, mask_path, hand_path, hand_mask_path, save_video_path, variables,
                end_color
            )
            try:
                ff_stat = ffmpeg_convert(source_vid=save_video_path, dest_vid=ffmpeg_video_path, platform=platform)
                if ff_stat:
                    final_result = {"status": True, "message": f"{ffmpeg_video_path}"}
                    os.unlink(save_video_path)
                    print(f"removed raw video: {save_video_path}")
                else:
                    final_result = {"status": True, "message": f"{save_video_path}"}
            except Exception as e:
                print(f"FFMPEG Error: {e}")
                final_result = {"status": True, "message": f"{save_video_path}"}
        except Exception as e:
            print(f"Error: {e}")
            final_result = {"status": False, "message": f"Error: {e}"}

    except Exception as e:
        print(f"Error: {e}")
        final_result = {"status": False, "message": f"Error: {e}"}
    Clock.schedule_once(lambda dt: callback(final_result))

def get_split_lens(image_path, max_1080p=True):
    """ Get image width & height. If the resolution is not standard & split length is not a common divisor, get the nearest standard resolution """
    final_return = {"image_res": [], "split_lens": []}
    hcf_list = []
    try:
        image_bgr = cv2.imread(image_path)
        #image_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        img_ht, img_wd = image_bgr.shape[0], image_bgr.shape[1]
        if max_1080p and (img_ht > 1920 or img_wd > 1920):
            if img_wd > img_ht: # 16:9
                img_wd = 1920
                img_ht = 1080
            else: # 9:16
                img_ht = 1920
                img_wd = 1080
        else:
            aspect_ratio = img_wd / img_ht
            img_ht = find_nearest_res(img_ht)
            new_aspect_wd = int(img_ht * aspect_ratio)
            img_wd = find_nearest_res(new_aspect_wd)
        hcf_list = common_divisors(img_ht, img_wd)
        # update the results
        final_return["split_lens"] = hcf_list
        final_return["image_res"] = [img_wd, img_ht]
    except Exception as e:
        print(f"Error while getting split len: {e}")
    return final_return # list of split length

# End