import UIKit
import Social
import UniformTypeIdentifiers
import os

private let shareLogger = Logger(subsystem: "se.enklagrejer.minarecept.share", category: "Share")

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

        // Some apps (including some recipe apps) don't attach a URL item at all.
        // They may embed the URL in extension item text fields or in the compose text.
        let extensionItemText = extensionItems
            .compactMap { $0.attributedContentText?.string }
            .joined(separator: "\n")
        let preflightTextCandidates = [
            self.contentText,
            self.textView.text ?? "",
            extensionItemText,
        ].filter { !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }

        for t in preflightTextCandidates {
            if let url = self.extractURL(from: t) {
                shareLogger.info("Found URL in preflight text (len=\(t.count)).")
                self.uploadURL(url)
                return
            }
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
                
                // Fallback 2: loadItem for text-like UTIs (ICA/HelloFresh/etc. often share as text)
                let textTypeIdentifiers = [
                    UTType.plainText.identifier,
                    UTType.utf8PlainText.identifier,
                    UTType.text.identifier,
                ]

                for typeId in textTypeIdentifiers {
                    if provider.hasItemConformingToTypeIdentifier(typeId) {
                        provider.loadItem(forTypeIdentifier: typeId) { [weak self] (item, error) in
                            guard let self else { return }
                            if let error {
                                shareLogger.error("Failed to load text item (\(typeId, privacy: .public)): \(String(describing: error), privacy: .public)")
                                DispatchQueue.main.async {
                                    self.showEphemeralNoticeAndComplete(message: "Kunde inte spara")
                                }
                                return
                            }

                            if let url = self.extractURL(fromItem: item) ?? self.extractURL(from: self.contentText) {
                                self.uploadURL(url)
                            } else {
                                let cls = item.map { String(describing: type(of: $0)) } ?? "nil"
                                shareLogger.error("No URL found in shared text (\(typeId, privacy: .public)). itemClass=\(cls, privacy: .public) contentTextLen=\(self.contentText.count)")
                                DispatchQueue.main.async {
                                    self.showEphemeralNoticeAndComplete(message: "Ingen länk hittades")
                                }
                            }
                        }
                        return
                    }
                }

                // Fallback 3: attempt to load any URL/text/data UTI we got and extract a link from it.
                for typeId in provider.registeredTypeIdentifiers {
                    guard let ut = UTType(typeId) else { continue }
                    let isCandidate = ut.conforms(to: .url) || ut.conforms(to: .text) || ut.conforms(to: .data)
                    guard isCandidate else { continue }

                    provider.loadItem(forTypeIdentifier: typeId) { [weak self] (item, error) in
                        guard let self else { return }
                        if let error {
                            shareLogger.error("Failed to load item (\(typeId, privacy: .public)): \(String(describing: error), privacy: .public)")
                            DispatchQueue.main.async {
                                self.showEphemeralNoticeAndComplete(message: "Kunde inte spara")
                            }
                            return
                        }

                        if let url = self.extractURL(fromItem: item) ?? self.extractURL(from: self.contentText) {
                            self.uploadURL(url)
                        } else {
                            if let image = item as? UIImage {
                                self.uploadImage(image)
                                return
                            }
                            let cls = item.map { String(describing: type(of: $0)) } ?? "nil"
                            shareLogger.error("No URL found in shared item (\(typeId, privacy: .public)). itemClass=\(cls, privacy: .public) contentTextLen=\(self.contentText.count)")
                            DispatchQueue.main.async {
                                self.showEphemeralNoticeAndComplete(message: "Ingen länk hittades")
                            }
                        }
                    }
                    return
                }
            }
        }

        // If we got here, we didn't find any usable attachments.
        DispatchQueue.main.async {
            if let url = self.extractURL(from: self.contentText) {
                self.uploadURL(url)
            } else {
                self.showEphemeralNoticeAndComplete(message: "Ingen länk hittades")
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

    private func extractURL(fromItem item: NSSecureCoding?) -> URL? {
        if item == nil { return nil }

        if let url = item as? URL {
            // If it's a file URL, try to read contents and extract a web URL from it.
            if url.isFileURL, let data = try? Data(contentsOf: url), data.count < 400_000 {
                if let s = String(data: data, encoding: .utf8), let found = extractURL(from: s) { return found }
                if let s = String(data: data, encoding: .utf16), let found = extractURL(from: s) { return found }
            }
            return url
        }

        if let text = coerceText(from: item), let found = extractURL(from: text) {
            return found
        }

        // Some apps share a dictionary/array payload (e.g. a property list) containing the URL as a value.
        if let dict = item as? NSDictionary {
            return extractURL(fromAnyCollection: dict)
        }
        if let arr = item as? NSArray {
            return extractURL(fromAnyCollection: arr)
        }

        if let data = item as? Data {
            // Try JSON / property list -> then recurse.
            if let obj = try? JSONSerialization.jsonObject(with: data),
               let found = extractURL(fromAnyCollection: obj as AnyObject) {
                return found
            }
            if let obj = try? PropertyListSerialization.propertyList(from: data, options: [], format: nil),
               let found = extractURL(fromAnyCollection: obj as AnyObject) {
                return found
            }
        }

        return nil
    }

    private func extractURL(fromAnyCollection obj: AnyObject) -> URL? {
        // NSDictionary / NSArray traversal, best-effort.
        if let s = obj as? String { return extractURL(from: s) }
        if let url = obj as? URL { return url }
        if let data = obj as? Data {
            if let s = String(data: data, encoding: .utf8) { return extractURL(from: s) }
            if let s = String(data: data, encoding: .utf16) { return extractURL(from: s) }
            return nil
        }
        if let dict = obj as? NSDictionary {
            for (_, v) in dict {
                if let found = extractURL(fromAnyCollection: v as AnyObject) { return found }
            }
            return nil
        }
        if let arr = obj as? NSArray {
            for v in arr {
                if let found = extractURL(fromAnyCollection: v as AnyObject) { return found }
            }
            return nil
        }
        return nil
    }

    private func coerceText(from item: NSSecureCoding?) -> String? {
        if item == nil { return nil }

        if let s = item as? String {
            return s
        }
        if let a = item as? NSAttributedString {
            return a.string
        }
        if let data = item as? Data {
            // Try UTF-8 first, then UTF-16
            if let s = String(data: data, encoding: .utf8) { return s }
            if let s = String(data: data, encoding: .utf16) { return s }
            return nil
        }
        if let url = item as? URL {
            // Could be a file URL pointing to a text file
            if url.isFileURL, let data = try? Data(contentsOf: url), data.count < 200_000 {
                if let s = String(data: data, encoding: .utf8) { return s }
                if let s = String(data: data, encoding: .utf16) { return s }
            }
            return url.absoluteString
        }
        return nil
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
            // Fallback: open the main app and let it import using its own auth.
            DispatchQueue.main.async {
                self.openMainAppForImport(url)
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
                    // Fallback: open app, let user retry/import there.
                    self.openMainAppForImport(url)
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
                        // Fallback: open app, where we can show better errors and retry.
                        self.openMainAppForImport(url)
                    }
                    return
                }
            }

            DispatchQueue.main.async {
                self.openMainAppForImport(url)
            }
        }
        task.resume()
    }

    private func uploadImage(_ image: UIImage) {
        guard let jpeg = image.jpegData(compressionQuality: 0.85) else {
            self.showEphemeralNoticeAndComplete(message: "Kunde inte läsa bild")
            return
        }

        let apiUrl = apiBaseURL.appendingPathComponent("recipes/import-image/")
        var request = URLRequest(url: apiUrl)
        request.httpMethod = "POST"

        let sharedDefaults = UserDefaults(suiteName: AppGroupConfig.suiteName)
        let token = sharedDefaults?.string(forKey: AppGroupConfig.tokenKey) ?? ""
        if token.isEmpty {
            DispatchQueue.main.async {
                self.showEphemeralNoticeAndComplete(message: "Logga in i appen först")
            }
            return
        }
        request.setValue("Token \(token)", forHTTPHeaderField: "Authorization")

        let boundary = "Boundary-\(UUID().uuidString)"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        var body = Data()
        func append(_ s: String) { body.append(Data(s.utf8)) }

        append("--\(boundary)\r\n")
        append("Content-Disposition: form-data; name=\"dish_type\"\r\n\r\n")
        append("\(selectedDishType.id)\r\n")

        append("--\(boundary)\r\n")
        append("Content-Disposition: form-data; name=\"image\"; filename=\"share.jpg\"\r\n")
        append("Content-Type: image/jpeg\r\n\r\n")
        body.append(jpeg)
        append("\r\n")
        append("--\(boundary)--\r\n")

        request.httpBody = body

        shareLogger.info("Attempting import from shared image (bytes=\(jpeg.count))")

        let task = URLSession.shared.dataTask(with: request) { [weak self] data, response, error in
            guard let self else { return }

            if let error {
                shareLogger.error("Image upload error: \(String(describing: error), privacy: .public)")
                DispatchQueue.main.async {
                    self.showEphemeralNoticeAndComplete(message: "Kunde inte spara")
                }
                return
            }

            if let http = response as? HTTPURLResponse {
                shareLogger.info("Image upload HTTP status: \(http.statusCode)")
                if http.statusCode == 201 || http.statusCode == 200 {
                    DispatchQueue.main.async {
                        self.showEphemeralNoticeAndComplete(message: "Sparad till MinaRecept")
                    }
                } else {
                    if let data, let body = String(data: data, encoding: .utf8) {
                        shareLogger.error("Image import failed body: \(body, privacy: .public)")
                    }
                    DispatchQueue.main.async {
                        self.showEphemeralNoticeAndComplete(message: "Kunde inte spara")
                    }
                }
                return
            }

            DispatchQueue.main.async {
                self.showEphemeralNoticeAndComplete(message: "Kunde inte spara")
            }
        }
        task.resume()
    }

    private func openMainAppForImport(_ url: URL) {
        // Open the main app via URL scheme and let it perform the import (it has Keychain auth).
        var components = URLComponents()
        components.scheme = "receptapp"
        components.host = "import"
        components.queryItems = [URLQueryItem(name: "url", value: url.absoluteString)]
        guard let deepLink = components.url else {
            self.showEphemeralNoticeAndComplete(message: "Kunde inte spara")
            return
        }

        shareLogger.info("Falling back to open main app for import: \(deepLink.absoluteString, privacy: .public)")
        self.extensionContext?.open(deepLink, completionHandler: { _ in
            // Even if open fails, just close the extension to avoid hanging.
            self.extensionContext?.completeRequest(returningItems: [], completionHandler: nil)
        })
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

        // Auto-dismiss (a bit longer so it's actually noticeable).
        DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) {
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

        func containsAny(_ needles: [String]) -> Bool {
            for n in needles where s.contains(n) { return true }
            return false
        }

        // Order matters: pick more specific categories first.
        // Dessert/Bak/Fika
        if containsAny([
            "efterratt", "dessert", "fika",
            "bak", "baka", "bakverk",
            "kaka", "kladdkaka", "brownie",
            "muffin", "cupcake",
            "tarta", "paj", "cheesecake",
            "semla", "kanelbulle", "bulle",
            "lussekatt", "lussebull", "saffran",
            "pepparkaka", "marang",
            "glass", "sorbet",
            "cookie"
        ]) {
            return "dessert"
        }
        // Förrätt / Tilltugg
        if containsAny(["forratt", "appetizer", "starter", "snittar", "tapas", "tilltugg", "plockmat"]) {
            return "appetizer"
        }
        // Frukost
        if containsAny(["frukost", "breakfast", "grot", "smoothie", "granola", "musli", "yoghurt", "overnight"]) {
            return "breakfast"
        }
        // If lunch/dinner is mentioned, it should win over broader tags like vegetarian.
        if s.contains("lunch") || s.contains("middag") || s.contains("dinner") {
            return "lunch_dinner"
        }
        if containsAny(["mellanmal", "snack"]) {
            return "snack"
        }
        if containsAny(["vegetar", "vegetarian", "vegan", "tofu", "halloumi", "quorn", "falafel", "lins", "linser"]) {
            return "vegetarian"
        }
        if containsAny(["fest", "party", "buffe", "bjudning"]) {
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
