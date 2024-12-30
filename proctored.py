import cv2
import dlib
import mediapipe as mp
import numpy as np
import os
import time
from typing import Tuple, List

class FaceAnalysisSystem:
    def __init__(self, face_recognition_model_path: str):
        # Face detection remains the same using dlib
        self.detector = dlib.get_frontal_face_detector()
        self.predictor = dlib.shape_predictor(face_recognition_model_path)
        self.face_rec_model = None  # dlib's face recognition model remains unchanged if needed
        self.reference_encodings = []
        self.face_match_threshold = 0.6  # Threshold for face recognition
        self.base_pitch = None  # Initialize the base pitch value
        self.base_yaw = None  # Initialize the base yaw value
        self.base_roll = None  # Initialize the base roll value

        # 3D Model points for head pose estimation
        self.model_points = np.array([
            (0.0, 0.0, 0.0),          # Nose tip
            (0.0, -330.0, -65.0),     # Chin
            (-225.0, 170.0, -135.0),  # Left eye left corner
            (225.0, 170.0, -135.0),   # Right eye right corner
            (-150.0, -150.0, -125.0), # Left mouth corner
            (150.0, -150.0, -125.0)   # Right mouth corner
        ], dtype=np.float32)

        self.camera_matrix = np.array([
            [640, 0, 320],
            [0, 640, 240],
            [0, 0, 1]
        ], dtype=np.float32)
        self.dist_coeffs = np.zeros((4, 1))

        # Initialize mediapipe face mesh for head pose estimation
        self.landmark_detector = mp.solutions.face_mesh.FaceMesh(min_detection_confidence=0.2, min_tracking_confidence=0.5)

    def encode_face(self, frame: np.ndarray) -> List[np.ndarray]:
        # Convert the frame to RGB for mediapipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.landmark_detector.process(rgb_frame)
        encodings = []
        if results.multi_face_landmarks:
            for landmarks in results.multi_face_landmarks:
                encoding = np.array([point for point in landmarks.landmark])
                encodings.append(encoding)
        return encodings

    def load_reference_images(self, folder_path: str) -> bool:
        try:
            for filename in os.listdir(folder_path):
                file_path = os.path.join(folder_path, filename)
                image = cv2.imread(file_path)
                if image is not None:
                    encodings = self.encode_face(image)
                    if encodings:
                        self.reference_encodings.append(encodings[0])
            return len(self.reference_encodings) > 0
        except Exception as e:
            print(f"Error loading reference images: {e}")
            return False

    def check_suspicious_activity(self, current_encoding: np.ndarray) -> float:
        if not self.reference_encodings:
            return float('inf')
        distances = [np.linalg.norm(ref - current_encoding) for ref in self.reference_encodings]
        return min(distances)

    def estimate_head_pose(self, landmarks) -> Tuple[float, float, float]:
        # Only estimate head pose using mediapipe landmarks (2D image points)
        image_points = np.array([
            (landmarks[1].x, landmarks[1].y),  # Nose tip
            (landmarks[8].x, landmarks[8].y),  # Chin
            (landmarks[36].x, landmarks[36].y),  # Left eye left corner
            (landmarks[45].x, landmarks[45].y),  # Right eye right corner
            (landmarks[48].x, landmarks[48].y),  # Left mouth corner
            (landmarks[54].x, landmarks[54].y)   # Right mouth corner
        ], dtype=np.float32)

        success, rotation_vector, _ = cv2.solvePnP(
            self.model_points, image_points, self.camera_matrix, self.dist_coeffs
        )

        rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
        yaw = np.arctan2(rotation_matrix[1][0], rotation_matrix[0][0]) * 180 / np.pi
        pitch = np.arctan2(-rotation_matrix[2][0], np.sqrt(rotation_matrix[2][1]**2 + rotation_matrix[2][2]**2)) * 180 / np.pi
        roll = np.arctan2(rotation_matrix[2][1], rotation_matrix[2][2]) * 180 / np.pi  # Calculate roll

        return yaw, pitch, roll

    def determine_head_position(self, yaw: float, pitch: float, roll: float) -> str:
        """
        Determines the head position based on yaw, pitch, and roll.
        - Yaw: Left/Right tilt
        - Pitch: Up/Down tilt
        - Roll: Left/Right rotation
        """
        if self.base_pitch is None:
            self.base_pitch = pitch
            self.base_yaw = yaw
            self.base_roll = roll

        adjusted_pitch = pitch - self.base_pitch
        adjusted_yaw = yaw - self.base_yaw
        adjusted_roll = roll - self.base_roll  # Adjust based on initial roll

        if abs(adjusted_yaw) > 15:  # Yaw-based movement detection
            if adjusted_yaw < 0:
                position = "Turned Left"
            else:
                position = "Turned Right"
        elif abs(adjusted_roll) > 15:  # Roll-based movement detection
            if adjusted_roll < 0:
                position = "Tilted Left"
            else:
                position = "Tilted Right"
        elif adjusted_pitch < -20:  # Upward head tilt
            position = "Looking Up"
        elif adjusted_pitch > 20:  # Downward head tilt
            position = "Looking Down"
        else:
            position = "Centered"  # Normal, centered position

        return position


def capture_reference_images(output_folder: str, num_images: int = 5):
    cap = cv2.VideoCapture(0)
    os.makedirs(output_folder, exist_ok=True)
    print(f"Capturing {num_images} reference images...")
    for i in range(num_images):
        ret, frame = cap.read()
        if ret:
            file_path = os.path.join(output_folder, f"reference_{i}.jpg")
            cv2.imwrite(file_path, frame)
            print(f"Captured: {file_path}")
            time.sleep(1)
    cap.release()

def main():
    system = FaceAnalysisSystem(
        face_recognition_model_path="backend/dlib_face_recognition_resnet_model_v1.dat"
    )

    reference_folder = "output/reference_images"
    capture_reference_images(reference_folder, num_images=5)

    if not system.load_reference_images(reference_folder):
        print("Error: Could not load reference images.")
        return

    print("Reference images loaded successfully!")

    cap = cv2.VideoCapture(0)

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Use dlib for face detection
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = system.detector(gray)

            for face in faces:
                # Get landmarks using dlib's shape predictor
                landmarks = system.predictor(frame, face)
                current_encoding = np.array([point for point in landmarks.parts()])
                
                # Use mediapipe for head pose estimation
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = system.landmark_detector.process(rgb_frame)

                for mp_landmarks in results.multi_face_landmarks:
                    yaw, pitch, roll = system.estimate_head_pose(mp_landmarks.landmark)
                    position = system.determine_head_position(yaw, pitch, roll)

                    # Calculate suspicious activity
                    distance = system.check_suspicious_activity(current_encoding)

                    if distance <= system.face_match_threshold:
                        status = "Match"
                        color = (0, 255, 0)
                    else:
                        status = "Suspicious"
                        color = (0, 0, 255)

                    # Annotate the frame
                    cv2.rectangle(frame, (face.left(), face.top()), (face.right(), face.bottom()), color, 2)
                    cv2.putText(frame, f"{status} - Dist: {distance:.2f}", (face.left(), face.top() - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)

                    cv2.putText(frame, f"Head Pose: {position}", (face.left(), face.bottom() + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

            # Display the image with annotations
            cv2.imshow("Face Detection and Head Pose", frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
