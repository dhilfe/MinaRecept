import SwiftUI
import UIKit

/// Detects when a tab is selected, including re-selecting the currently active tab.
/// SwiftUI's `TabView` doesn't expose a direct callback for re-taps, so we bridge via UIKit.
struct TabReselectDetector: UIViewControllerRepresentable {
    typealias OnSelect = (Int) -> Void

    let onSelect: OnSelect

    func makeUIViewController(context: Context) -> UIViewController {
        let controller = ObserverViewController()
        controller.onUpdate = { [weak coordinator = context.coordinator, weak controller] in
            guard let coordinator, let controller else { return }
            coordinator.attach(to: controller)
        }
        return controller
    }

    func updateUIViewController(_ uiViewController: UIViewController, context: Context) {
        (uiViewController as? ObserverViewController)?.onUpdate = { [weak coordinator = context.coordinator, weak uiViewController] in
            guard let coordinator, let uiViewController else { return }
            coordinator.attach(to: uiViewController)
        }
        context.coordinator.attach(to: uiViewController)
    }

    func makeCoordinator() -> Coordinator {
        Coordinator(onSelect: onSelect)
    }

    final class ObserverViewController: UIViewController {
        var onUpdate: (() -> Void)?

        override func viewDidAppear(_ animated: Bool) {
            super.viewDidAppear(animated)
            onUpdate?()
        }

        override func viewWillAppear(_ animated: Bool) {
            super.viewWillAppear(animated)
            onUpdate?()
        }

        override func didMove(toParent parent: UIViewController?) {
            super.didMove(toParent: parent)
            onUpdate?()
        }

        override func viewDidLayoutSubviews() {
            super.viewDidLayoutSubviews()
            onUpdate?()
        }
    }

    final class Coordinator: NSObject, UIGestureRecognizerDelegate, UITabBarControllerDelegate {
        private let onSelect: OnSelect
        private weak var tabBarController: UITabBarController?
        private weak var tabBar: UITabBar?
        private weak var tapRecognizer: UITapGestureRecognizer?
        private weak var forwardedTabBarControllerDelegate: (any UITabBarControllerDelegate)?

        init(onSelect: @escaping OnSelect) {
            self.onSelect = onSelect
        }

        func attach(to controller: UIViewController) {
            guard let tbc = controller.tabBarController else { return }
            if tabBarController !== tbc {
                tabBarController = tbc
                attachDelegate(to: tbc)
                attachTapRecognizer(to: tbc)
            } else {
                // Ensure recognizer is still attached (some UIKit flows recreate tab bar views).
                attachDelegate(to: tbc)
                attachTapRecognizer(to: tbc)
            }
        }

        private func attachDelegate(to tabBarController: UITabBarController) {
            // Add a delegate-based reselect signal as a backup. Forward to any existing delegate.
            if tabBarController.delegate !== self {
                forwardedTabBarControllerDelegate = tabBarController.delegate
                tabBarController.delegate = self
            }
        }

        private func attachTapRecognizer(to tabBarController: UITabBarController) {
            let bar = tabBarController.tabBar

            // Already attached to this tab bar.
            if tabBar === bar, tapRecognizer != nil {
                return
            }

            // If we were attached to a previous tab bar instance, detach.
            if let oldBar = tabBar, let recognizer = tapRecognizer {
                oldBar.removeGestureRecognizer(recognizer)
            }

            tabBar = bar

            let recognizer = UITapGestureRecognizer(target: self, action: #selector(handleTabBarTap(_:)))
            recognizer.cancelsTouchesInView = false
            recognizer.delegate = self
            bar.addGestureRecognizer(recognizer)
            tapRecognizer = recognizer
        }

        @objc private func handleTabBarTap(_ recognizer: UITapGestureRecognizer) {
            guard recognizer.state == .ended,
                  let bar = tabBar,
                  let items = bar.items,
                  !items.isEmpty,
                  let tbc = tabBarController
            else { return }

            let location = recognizer.location(in: bar)

            // Prefer using actual UITabBarButton frames for correctness across insets/layout.
            let tabBarButtons: [UIControl] = bar.subviews
                .compactMap { $0 as? UIControl }
                .filter { String(describing: type(of: $0)).contains("UITabBarButton") }
                .sorted { $0.frame.minX < $1.frame.minX }

            let tappedIndex: Int?
            if let idx = tabBarButtons.firstIndex(where: { $0.frame.contains(location) }) {
                tappedIndex = idx
            } else {
                // Fallback: proportional calculation.
                let width = max(bar.bounds.width, 1)
                let itemWidth = width / CGFloat(items.count)
                let idx = Int(location.x / itemWidth)
                tappedIndex = (idx >= 0 && idx < items.count) ? idx : nil
            }

            guard let tappedIndex else { return }

            // Only treat as a "reselect" when the user taps the currently selected tab.
            if tappedIndex == tbc.selectedIndex {
                onSelect(tappedIndex)
            }
        }

        // Allow the tab bar to continue handling taps normally.
        func gestureRecognizer(_ gestureRecognizer: UIGestureRecognizer, shouldReceive touch: UITouch) -> Bool {
            true
        }

        func tabBarController(_ tabBarController: UITabBarController, shouldSelect viewController: UIViewController) -> Bool {
            // This gets called even when tapping the already-selected tab.
            if viewController === tabBarController.selectedViewController {
                onSelect(tabBarController.selectedIndex)
            }

            if let forwardedTabBarControllerDelegate,
               forwardedTabBarControllerDelegate.responds(to: #selector(UITabBarControllerDelegate.tabBarController(_:shouldSelect:))) {
                return forwardedTabBarControllerDelegate.tabBarController?(tabBarController, shouldSelect: viewController) ?? true
            }

            return true
        }
    }
}
