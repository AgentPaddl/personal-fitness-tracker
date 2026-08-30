import SwiftUI
import UIKit

extension View {
    /// Dismisses whichever text field/editor currently has keyboard focus
    /// when the user taps anywhere in this view, without intercepting taps
    /// meant for buttons, pickers, or list/form rows - `simultaneousGesture`
    /// observes the tap alongside existing gestures rather than consuming
    /// it, so existing text-entry and control behavior is unchanged.
    ///
    /// SwiftUI has no built-in "dismiss whichever field is focused,
    /// wherever it lives" API that works across nested child views (e.g.
    /// `WorkoutSetRow`'s text fields inside `WorkoutSessionView`) without
    /// threading a `FocusState` binding through every intermediate view's
    /// initializer - resigning the current first responder is the
    /// standard, minimal-footprint way to do this uniformly across screens.
    func dismissesKeyboardOnBackgroundTap() -> some View {
        simultaneousGesture(
            TapGesture().onEnded {
                UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil)
            }
        )
    }
}
