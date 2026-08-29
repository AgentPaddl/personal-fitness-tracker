import SwiftUI
import UIKit

/// Thin UIKit bridge for camera capture. Uses `UIImagePickerController`
/// (not `PHPickerViewController`, which cannot present the camera) as the
/// smallest robust way to capture a photo. Never saves the captured photo
/// to the Photos library - only the default, non-saving behavior of
/// `UIImagePickerController` is used.
struct CameraCaptureView: UIViewControllerRepresentable {
    var onCapture: (Data) -> Void
    var onCancel: () -> Void

    func makeUIViewController(context: Context) -> UIImagePickerController {
        let controller = UIImagePickerController()
        controller.sourceType = .camera
        controller.allowsEditing = false
        controller.delegate = context.coordinator
        return controller
    }

    func updateUIViewController(_ uiViewController: UIImagePickerController, context: Context) {}

    func makeCoordinator() -> Coordinator {
        Coordinator(onCapture: onCapture, onCancel: onCancel)
    }

    final class Coordinator: NSObject, UIImagePickerControllerDelegate, UINavigationControllerDelegate {
        private let onCapture: (Data) -> Void
        private let onCancel: () -> Void

        init(onCapture: @escaping (Data) -> Void, onCancel: @escaping () -> Void) {
            self.onCapture = onCapture
            self.onCancel = onCancel
        }

        func imagePickerController(
            _ picker: UIImagePickerController,
            didFinishPickingMediaWithInfo info: [UIImagePickerController.InfoKey: Any]
        ) {
            guard let image = info[.originalImage] as? UIImage, let data = image.jpegData(compressionQuality: 0.9)
            else {
                onCancel()
                return
            }
            onCapture(data)
        }

        func imagePickerControllerDidCancel(_ picker: UIImagePickerController) {
            onCancel()
        }
    }
}
