from statistics import mode

import cv2
import sys
import base64
from keras.models import load_model
import numpy as np

from utils.datasets import get_labels
from utils.inference import detect_faces
from utils.inference import draw_text
from utils.inference import draw_bounding_box
from utils.inference import apply_offsets
from utils.inference import load_detection_model
from utils.preprocessor import preprocess_input

from skimage.color import rgb2gray
from scipy.ndimage.filters import gaussian_filter
from skimage.filters import threshold_otsu
from skimage.io import imsave

# parameters for loading data and images
detection_model_path = '../trained_models/detection_models/haarcascade_frontalface_default.xml'
emotion_model_path = '../trained_models/emotion_models/fer2013_mini_XCEPTION.102-0.66.hdf5'
emotion_labels = get_labels('fer2013')

# hyper-parameters for bounding boxes shape
frame_window = 10
emotion_offsets = (20, 40)

# loading models
face_detection = load_detection_model(detection_model_path)
emotion_classifier = load_model(emotion_model_path, compile=False)

# getting input model shapes for inference
emotion_target_size = emotion_classifier.input_shape[1:3]

# starting lists for calculating modes
emotion_window = []

def xdog(im, gamma=0.98, phi=200, eps=-0.1, k=1.6, sigma=0.8, binarize=False):
    # Source : https://github.com/CemalUnal/XDoG-Filter
    # Reference : XDoG: An eXtended difference-of-Gaussians compendium including advanced image stylization
    # Link : http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.365.151&rep=rep1&type=pdf
    imf1 = gaussian_filter(im, sigma)
    imf2 = gaussian_filter(im, sigma * k)
    imdiff = imf1 - gamma * imf2
    imdiff = (imdiff < eps) * 1.0  + (imdiff >= eps) * (1.0 + np.tanh(phi * imdiff))
    imdiff -= imdiff.min()
    imdiff /= imdiff.max()
    if binarize:
        th = threshold_otsu(imdiff)
        imdiff = imdiff >= th
    imdiff = imdiff.astype('float32')
    return imdiff

# def decode_base64(data, altchars=b'+/'):
#     """Decode base64, padding being optional.

#     :param data: Base64 data as an ASCII byte string
#     :returns: The decoded byte string.

#     """
#     data = re.sub(rb'[^a-zA-Z0-9%s]' % altchars, b'', data)  # normalize
#     missing_padding = len(data) % 4
#     if missing_padding:
#         data += b'='* (4 - missing_padding)
#     return base64.b64decode(data, altchars)

def main(imageBase64):
    imageBase64 += "=" * ((4 - len(imageBase64) % 4) % 4)
    with open("pictures/original/original.png", 'wb') as f:
        f.write(base64.b64decode(imageBase64))
    bgr_image = cv2.imread("pictures/original/original.png")
    gray_image = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2GRAY)
    rgb_image = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
    faces = detect_faces(face_detection, gray_image)

    for face_coordinates in faces:
        x1, x2, y1, y2 = apply_offsets(face_coordinates, emotion_offsets)
        gray_face = gray_image[y1:y2, x1:x2]
        try:
            gray_face = cv2.resize(gray_face, (emotion_target_size))
        except:
            continue

        gray_face = preprocess_input(gray_face, True)
        gray_face = np.expand_dims(gray_face, 0)
        gray_face = np.expand_dims(gray_face, -1)
        emotion_prediction = emotion_classifier.predict(gray_face)
        emotion_probability = np.max(emotion_prediction)
        emotion_label_arg = np.argmax(emotion_prediction)
        emotion_text = emotion_labels[emotion_label_arg]
        emotion_window.append(emotion_text)

        x, y, w, h = face_coordinates
        roi_color = bgr_image[y:y + h, x:x + w]
        print("[INFO] Object found. Saving locally.")
        cv2.imwrite('pictures/face/' + str(w) + str(h) + '_faces.jpg', roi_color)
        im = cv2.imread('pictures/face/' + str(w) + str(h) + '_faces.jpg')
        imgray = cv2.cvtColor(im,cv2.COLOR_BGR2GRAY)
        # ret,thresh = cv2.threshold(imgray,127,255,0)
        # contours, hierarchy = cv2.findContours(thresh,cv2.RETR_TREE,cv2.CHAIN_APPROX_SIMPLE)
        # img = cv2.drawContours(imgray, contours, -1, (255,255,255), 7)
        # img = (255 - img)
        # cv2.imwrite(str(w) + str(h) + '_faces_contours.jpg', img)
        # cv2.imwrite('pictures/' + str(w) + str(h) + '_faces_grey.jpg', imgray)
        xdogim = xdog(imgray, binarize=True, k=2)
        imsave('pictures/contour/' + str(w) + str(h) + '_faces_grey.jpg', xdogim)

        if len(emotion_window) > frame_window:
            emotion_window.pop(0)
        try:
            emotion_mode = mode(emotion_window)
        except:
            continue

        if emotion_text == 'angry':
            color = emotion_probability * np.asarray((255, 0, 0))
        elif emotion_text == 'sad':
            color = emotion_probability * np.asarray((0, 0, 255))
        elif emotion_text == 'happy':
            color = emotion_probability * np.asarray((255, 255, 0))
        elif emotion_text == 'surprise':
            color = emotion_probability * np.asarray((0, 255, 255))
        else:
            color = emotion_probability * np.asarray((0, 255, 0))

        color = color.astype(int)
        color = color.tolist()

        draw_bounding_box(face_coordinates, rgb_image, color)
        draw_text(face_coordinates, rgb_image, emotion_mode,
                  color, 0, -45, 1, 1)

        return base64.b64encode(imsave('pictures/contour/' + str(w) + str(h) + '_faces_grey.jpg', xdogim))
main()