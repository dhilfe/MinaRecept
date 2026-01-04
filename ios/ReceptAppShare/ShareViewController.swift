import UIKit
import Social
import UniformTypeIdentifiers
import os

private let shareLogger = Logger(subsystem: "se.receptapp.ios.share", category: "Share")

private enum AppGroupConfig {
    static let suiteName = "group.se.enklagrejer.minarecept"
    static let tokenKey = "auth_token"
}

class ShareViewController: SLComposeServiceViewController {
    
    private var selectedDishType: (id: String, name: String) = ("lunch_dinner", "Lunch/Middag")
    private var didAutoGuessDishType = false
    private var sharedURL: URL?

    private static let dishTypes: [(id: String, name: String)] = [
        ("breakfast", "Frukost"),
        ("lunch_dinner", "Lunch/Middag"),
        ("appetizer", "Förrätt"),
        ("dessert", "Efterrätt"),
        ("snack", "Mellanmål"),
        ("party", "Fest"),
        ("vegetarian", "Vegetariskt"),
        ("other", "Övrigt"),
    ]

    override func isContentValid() -> Bool {
        // Do validation of contentText and/or NSExtensionContext attachments here
        return true
    }

    override func presentationAnimationDidFinish() {
        super.presentationAnimationDidFinish()

        // Safari often pre-fills the compose text with the page title, e.g. "Chokladbollar | Recept ICA.se".
        // Trim everything after the first pipe to avoid manual cleanup.
        if let current = self.textView.text, !current.isEmpty {
            let cleaned = Self.stripAfterPipe(current)
            if cleaned != current {
                self.textView.text = cleaned
            }
        }

        // Now that we likely have a title in the compose text, attempt to guess a good category.
        self.autoGuessDishTypeIfNeeded(title: self.textView.text, url: self.sharedURL)
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        self.loadSharedURLIfAvailable()
    }

    override func didSelectPost() {
        // This is called after the user selects Post. Do the upload of contentText and/or NSExtensionContext attachments.
        
        guard let extensionItems = extensionContext?.inputItems as? [NSExtensionItem] else {
            self.extensionContext?.completeRequest(returningItems: [], completionHandler: nil)
            return
        }

        for item in extensionItems {
            guard let attachments = item.attachments else { continue }

            for provider in attachments {
                // Debug: learn what other apps share (ICA/kokaihop, etc.).
                let utis = provider.registeredTypeIdentifiers.joined(separator: ", ")
                shareLogger.info("[DEBUG] attachment UTIs: \(utis, privacy: .public)")

                if provider.canLoadObject(ofClass: URL.self) {
                    _ = provider.loadObject(ofClass: URL.self) { [weak self] object, error in
                        if let error {
                            shareLogger.error("Failed to load URL object: \(String(describing: error), privacy: .public)")
                            self?.extensionContext?.completeRequest(returningItems: [], completionHandler: nil)
                            return
                        }
                        if let url = object {
                            self?.uploadURL(url)
                        } else {
                            self?.extensionContext?.completeRequest(returningItems: [], completionHandler: nil)
                        }
                    }
                    return // Handle only the first URL found
                }

                // Fallback 1: NSString object (e.g. Chrome/Notes sometimes)
                if provider.canLoadObject(ofClass: NSString.self) {
                    _ = provider.loadObject(ofClass: NSString.self) { [weak self] object, error in
                        if let error {
                            shareLogger.error("Failed to load String object: \(String(describing: error), privacy: .public)")
                            // Continue to try other providers or fallback methods
                        } else if let string = object as? String {
                            // ICA/Kokaihop might share "Check this link: https://..."
                            // Try to find a URL inside the string
                            if let url = self?.extractURL(from: string) {
                                self?.uploadURL(url)
                                return
                            }
                            
                            // If just a raw URL string
                            if let url = URL(string: string), url.scheme != nil {
                                self?.uploadURL(url)
                                return
                            }
                        }
                    }
                }
                
                // Fallback 2: loadItem(forTypeIdentifier: "public.plain-text")
                // This is needed for ICA app which fails on loadObject(ofClass: NSString.self)
                if provider.hasItemConformingToTypeIdentifier("public.plain-text") {
                    provider.loadItem(forTypeIdentifier: "public.plain-text") { [weak self] (item, error) in
                        if let error {
                            shareLogger.error("Failed to load plain-text item: \(String(describing: error), privacy: .public)")
                            return
                        }
                        
                        var text: String?
                        if let s = item as? String {
                            text = s
                        } else if let url = item as? URL {
                            // Sometimes item is a file URL to a text file? Or just the text itself?
                            // Try reading it? Or maybe it IS the web URL?
                            text = url.absoluteString
                        }
                        
                        if let text, let url = self?.extractURL(from: text) {
                            self?.uploadURL(url)
                        } else {
                            // Final failure
                            DispatchQueue.main.async {
                                self?.extensionContext?.completeRequest(returningItems: [], completionHandler: nil)
                            }
                        }
                    }
                    return
                }
            }
        }
    }

    override func configurationItems() -> [Any]! {
        let categoryItem = SLComposeSheetConfigurationItem()
        categoryItem?.title = "Kategori"
        categoryItem?.value = selectedDishType.name
        categoryItem?.tapHandler = { [weak self] in
            guard let self else { return }
            let selector = DishTypeSelectionViewController(
                dishTypes: Self.dishTypes,
                selectedId: self.selectedDishType.id
            ) { [weak self] selected in
                guard let self else { return }
                self.selectedDishType = selected
                self.didAutoGuessDishType = true
                self.reloadConfigurationItems()
                self.popConfigurationViewController()
            }
            self.pushConfigurationViewController(selector)
        }

        return [categoryItem as Any].compactMap { $0 }
    }

    private var apiBaseURL: URL {
        if
            let raw = Bundle.main.object(forInfoDictionaryKey: "API_BASE_URL") as? String,
            let url = URL(string: raw)
        {
            return url
        }

        return URL(string: "http://localhost:8000/api/")!
    }
    
    private func extractURL(from text: String) -> URL? {
        let detector = try? NSDataDetector(types: NSTextCheckingResult.CheckingType.link.rawValue)
        let matches = detector?.matches(in: text, options: [], range: NSRange(location: 0, length: text.utf16.count))
        return matches?.first?.url
    }
    
    private func uploadURL(_ url: URL) {
        shareLogger.info("Attempting import for shared URL: \(url.absoluteString, privacy: .public)")
        let apiUrl = apiBaseURL.appendingPathComponent("recipes/import/")
        
        var request = URLRequest(url: apiUrl)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let sharedDefaults = UserDefaults(suiteName: AppGroupConfig.suiteName)
        let token = sharedDefaults?.string(forKey: AppGroupConfig.tokenKey) ?? ""
        if token.isEmpty {
            shareLogger.error("[DEBUG] Missing shared token (App Groups). Cannot import from Share Extension.")
            let allKeys = sharedDefaults?.dictionaryRepresentation().keys.joined(separator: ", ") ?? "(no keys)"
            shareLogger.error("[DEBUG] App Group UserDefaults keys: \(allKeys)")
            DispatchQueue.main.async {
                self.showEphemeralNoticeAndComplete(message: "Kunde inte spara")
            }
            return
        }
        request.setValue("Token \(token)", forHTTPHeaderField: "Authorization")
        shareLogger.info("[DEBUG] Using shared token from App Group: \(token, privacy: .private)")
        
        let body: [String: Any] = [
            "url": url.absoluteString,
            "dish_type": selectedDishType.id,
        ]
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        
        let task = URLSession.shared.dataTask(with: request) { [weak self] data, response, error in
            guard let self = self else { return }

            if let error = error {
                if let urlError = error as? URLError {
                    print("ShareExtension upload URLError: \(urlError.code.rawValue) \(urlError.localizedDescription)")
                    shareLogger.error("Upload URLError: \(urlError.code.rawValue) \(urlError.localizedDescription, privacy: .public)")
                } else {
                    print("ShareExtension upload error: \(error)")
                    shareLogger.error("Upload error: \(String(describing: error), privacy: .public)")
                }

                DispatchQueue.main.async {
                    self.showEphemeralNoticeAndComplete(message: "Kunde inte spara")
                }
                return
            }

            if let httpResponse = response as? HTTPURLResponse {
                shareLogger.info("Upload HTTP status: \(httpResponse.statusCode)")
                if httpResponse.statusCode == 201 || httpResponse.statusCode == 200 {
                    DispatchQueue.main.async {
                        self.showEphemeralNoticeAndComplete(message: "Sparad till MinaRecept")
                    }
                    return
                } else {
                    print("Error status: \(httpResponse.statusCode)")

                    if let data, let body = String(data: data, encoding: .utf8) {
                        print("Response body: \(body)")
                    }

                    shareLogger.error("Import failed with HTTP \(httpResponse.statusCode)")

                    DispatchQueue.main.async {
                        self.showEphemeralNoticeAndComplete(message: "Kunde inte spara")
                    }
                    return
                }
            }

            DispatchQueue.main.async {
                self.showEphemeralNoticeAndComplete(message: "Kunde inte spara")
            }
        }
        task.resume()
    }

    private func showEphemeralNoticeAndComplete(message: String) {
        // Lightweight toast that doesn't require user interaction.
        let container = UIView()
        container.backgroundColor = UIColor.secondarySystemBackground.withAlphaComponent(0.95)
        container.layer.cornerRadius = 12
        container.layer.masksToBounds = true
        container.layoutMargins = UIEdgeInsets(top: 10, left: 14, bottom: 10, right: 14)
        container.isUserInteractionEnabled = false

        let label = UILabel()
        label.text = message
        label.textAlignment = .center
        label.numberOfLines = 2
        label.font = .preferredFont(forTextStyle: .subheadline)
        label.textColor = .label
        label.translatesAutoresizingMaskIntoConstraints = false

        container.translatesAutoresizingMaskIntoConstraints = false
        container.addSubview(label)
        view.addSubview(container)

        NSLayoutConstraint.activate([
            container.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            container.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 12),
            container.widthAnchor.constraint(lessThanOrEqualTo: view.widthAnchor, multiplier: 0.85),

            label.leadingAnchor.constraint(equalTo: container.layoutMarginsGuide.leadingAnchor),
            label.trailingAnchor.constraint(equalTo: container.layoutMarginsGuide.trailingAnchor),
            label.topAnchor.constraint(equalTo: container.layoutMarginsGuide.topAnchor),
            label.bottomAnchor.constraint(equalTo: container.layoutMarginsGuide.bottomAnchor),
        ])

        // Auto-dismiss quickly.
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.8) {
            container.removeFromSuperview()
            self.extensionContext?.completeRequest(returningItems: [], completionHandler: nil)
        }
    }

    private static func stripAfterPipe(_ text: String) -> String {
        // If the text contains a URL, remove the URL from the title display.
        // We only want to show descriptive text here.
        // E.g. "Check out this recipe https://ica.se/..." -> "Check out this recipe"
        // Or if it's just a URL, maybe show empty?
        
        // Simple heuristic: if it looks like a URL, remove it.
        // But let's keep the pipe logic first.
        
        var t = text.trimmingCharacters(in: .whitespacesAndNewlines)
        if let pipeIndex = t.firstIndex(of: "|") {
            t = t[..<pipeIndex].trimmingCharacters(in: .whitespacesAndNewlines)
        }
        
        // Remove URL if present in title
        if let detector = try? NSDataDetector(types: NSTextCheckingResult.CheckingType.link.rawValue) {
            let range = NSRange(location: 0, length: t.utf16.count)
            let matches = detector.matches(in: t, options: [], range: range)
            for match in matches.reversed() {
                if let r = Range(match.range, in: t) {
                    t.removeSubrange(r)
                }
            }
        }
        
        return t.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private func loadSharedURLIfAvailable() {
        guard let extensionItems = extensionContext?.inputItems as? [NSExtensionItem] else { return }

        for item in extensionItems {
            guard let attachments = item.attachments else { continue }
            for provider in attachments {
                if provider.canLoadObject(ofClass: URL.self) {
                    _ = provider.loadObject(ofClass: URL.self) { [weak self] object, error in
                        guard let self else { return }
                        if let error {
                            shareLogger.error("Failed to load URL for category guess: \(String(describing: error), privacy: .public)")
                            return
                        }
                        guard let url = object else { return }

                        DispatchQueue.main.async {
                            self.sharedURL = url
                            self.autoGuessDishTypeIfNeeded(title: self.textView.text, url: url)
                        }
                    }
                    return
                }

                // Fallback: URL inside plain text
                if provider.hasItemConformingToTypeIdentifier("public.plain-text") {
                     provider.loadItem(forTypeIdentifier: "public.plain-text") { [weak self] (item, error) in
                        guard let self else { return }
                        if let s = item as? String, let url = self.extractURL(from: s) {
                             DispatchQueue.main.async {
                                self.sharedURL = url
                                self.autoGuessDishTypeIfNeeded(title: self.textView.text, url: url)
                            }
                        }
                     }
                     return
                }
            }
        }
    }

    private func autoGuessDishTypeIfNeeded(title: String?, url: URL?) {
        guard !didAutoGuessDishType else { return }

        let guessedId = Self.guessDishTypeId(title: title, url: url)
        let guessed = Self.dishTypeTuple(forId: guessedId)

        // Only update if we actually changed something.
        if guessed.id != selectedDishType.id {
            selectedDishType = guessed
            shareLogger.info("Auto-selected dish type: \(guessed.id, privacy: .public)")
            self.reloadConfigurationItems()
        }

        didAutoGuessDishType = true
    }

    private static func dishTypeTuple(forId id: String) -> (id: String, name: String) {
        if let match = dishTypes.first(where: { $0.id == id }) {
            return match
        }
        return ("lunch_dinner", "Lunch/Middag")
    }

    private static func guessDishTypeId(title: String?, url: URL?) -> String {
        var haystack = ""
        if let title, !title.isEmpty {
            haystack += " " + title
        }
        if let url {
            haystack += " " + url.absoluteString
            haystack += " " + (url.host ?? "")
            haystack += " " + url.path
            haystack += " " + url.query.orEmpty
        }

        // Match diacritic-insensitive (e.g. efterrätt/efterratt).
        let s = haystack
            .folding(options: [.diacriticInsensitive, .caseInsensitive], locale: .current)
            .lowercased()

        // Order matters: pick more specific categories first.
        if s.contains("efterratt") || s.contains("dessert") || s.contains("kaka") || s.contains("tarta") || s.contains("cookie") {
            return "dessert"
        }
        if s.contains("forratt") || s.contains("appetizer") || s.contains("starter") {
            return "appetizer"
        }
        if s.contains("frukost") || s.contains("breakfast") {
            return "breakfast"
        }
        // If lunch/dinner is mentioned, it should win over broader tags like vegetarian.
        if s.contains("lunch") || s.contains("middag") || s.contains("dinner") {
            return "lunch_dinner"
        }
        if s.contains("mellanmal") || s.contains("snack") {
            return "snack"
        }
        if s.contains("vegetar") || s.contains("vegetarian") || s.contains("vegan") {
            return "vegetarian"
        }
        if s.contains("fest") || s.contains("party") {
            return "party"
        }

        return "lunch_dinner"
    }
}

private extension Optional where Wrapped == String {
    var orEmpty: String { self ?? "" }
}

final class DishTypeSelectionViewController: UITableViewController {
    private let dishTypes: [(id: String, name: String)]
    private let onSelect: ((id: String, name: String)) -> Void
    private var selectedId: String

    init(
        dishTypes: [(id: String, name: String)],
        selectedId: String,
        onSelect: @escaping ((id: String, name: String)) -> Void
    ) {
        self.dishTypes = dishTypes
        self.selectedId = selectedId
        self.onSelect = onSelect
        super.init(style: .insetGrouped)
        self.title = "Kategori"
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override func tableView(_ tableView: UITableView, numberOfRowsInSection section: Int) -> Int {
        dishTypes.count
    }

    override func tableView(_ tableView: UITableView, cellForRowAt indexPath: IndexPath) -> UITableViewCell {
        let cell = UITableViewCell(style: .default, reuseIdentifier: nil)
        let item = dishTypes[indexPath.row]
        cell.textLabel?.text = item.name
        cell.accessoryType = (item.id == selectedId) ? .checkmark : .none
        return cell
    }

    override func tableView(_ tableView: UITableView, didSelectRowAt indexPath: IndexPath) {
        let item = dishTypes[indexPath.row]
        selectedId = item.id
        tableView.reloadData()
        onSelect(item)
    }
}
