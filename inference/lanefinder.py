import cv2
import numpy as np
# from edgetpu.basic.basic_engine import BasicEngine
import pycoral.utils.edgetpu as etpu
from pycoral.adapters import common
from image.processing import preprocessing, postprocessing


class Lanefinder:

    def __init__(self, model, input_shape, output_shape, quant, dequant):
        self._window = None
        self.interpreter = self._get_tpu_engine(model)
        self.interpreter.allocate_tensors()
        self._cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
        self._size = input_shape
        self._output_shape = output_shape
        self._quant = quant
        self._dequant = dequant

        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()
        self.input_zero = self.input_details[0]['quantization'][1]
        self.input_scale = self.input_details[0]['quantization'][0]
        self.output_zero = self.output_details[0]['quantization'][1]
        self.output_scale = self.output_details[0]['quantization'][0]

    @property
    def window(self):
        return self._window

    @window.setter
    def window(self, name):
        self._window = name

    @staticmethod
    def _get_tpu_engine(model):
        try:
            # get runtime for TPU
            # model = BasicEngine(model)
            # Chan
            model = etpu.make_interpreter(model)

        except RuntimeError:
            # TPU has not been detected
            model = None

        return model

    def _preprocess(self, frame):
        # normalize and quantize input
        # with paramaeters obtained during
        # model calibration
        return preprocessing(frame, self._quant['mean'], self._quant['std'])

    def _postprocess(self, pred_obj, frame):
        # get predicted mask from pred object
        # reshape to output size
        # perform closing operation to smooth out lane edges
        # and overlay with original frame
        return postprocessing(
            pred_obj=pred_obj,
            frame=frame,
            mean=self._quant['mean'],
            std=self._quant['std'],
            in_shape=self._size,
            out_shape=self._output_shape
        )

    def stream(self):
        """
        Starts real time video stream with
        coral edgetpu supported traffic lane segmentation

        :return:    void
        """
        while True:
            # get next video frame
            ret, frame = self._cap.read()

            if not ret:
                # frame has not been
                # retrieved
                break

            frame = np.array(frame)
            frmcpy = frame.copy()

            frame = cv2.resize(frame, tuple(self._size))
            frame = frame.astype(np.float32)

            if self.interpreter is not None:
                # TPU engine has been initiated
                # so run inference steps
                frame = self._preprocess(frame)
                # Chan
                # pred_obj = self._engine.run_inference(frame.flatten())
                self.input_details = self.interpreter.get_input_details()
                self.interpreter.set_tensor(self.input_details[0]['index'], frame)
                self.interpreter.invoke()
                pred_obj = (common.output_tensor(self.interpreter, 0) - self.output_zero) * self.output_scale
                pred = self._postprocess(pred_obj, frmcpy)

            else:
                # no TPU detected so output recorded
                # frame with warning sign on it
                frmcpy = cv2.resize(frmcpy, self._output_shape)
                pred = cv2.putText(
                    frmcpy,
                    'TPU has not been detected!',
                    org=(self._output_shape[0] // 16, self._output_shape[1] // 2),
                    fontFace=cv2.FONT_HERSHEY_SIMPLEX,
                    fontScale=1,
                    color=(0, 0, 255),
                    thickness=1
                )

            if self._window is not None:
                # show in window with fullscreen setup
                cv2.imshow(self._window, pred)

            else:
                # user did not specify window name
                # for fullscreen use so use default opencv size
                cv2.imshow('default', pred)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                # exit on key press
                break

    def destroy(self):
        """
        Runs cleanup after main loop exit

        :return:    void
        """
        cv2.destroyAllWindows()
        self._cap.release()


class LanefinderFromVideo(Lanefinder):

    def __init__(self, src, model, input_shape, output_shape, quant, dequant):
        Lanefinder.__init__(self, model, input_shape, output_shape, quant, dequant)
        self._cap = cv2.VideoCapture(src)
