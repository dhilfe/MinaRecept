import UIKit
import Social
import UniformTypeIdentifiers
import os

private struct InstagramPreview {
    let captionText: String?
    let thumbnailURL: URL?
}

private let shareLogger = Logger(subsystem: "se.enklagrejer.minarecept.share", category: "Share")

private enum AppGroupConfig {
    static let suiteName = "group.se.enklagrejer.minarecept"
    static let tokenKey = "auth_token"
}

class ShareViewController: SLComposeServiceViewController {
    
    private var selectedDishType: (id: String, name: String) = ("lunch_dinner", "Lunch/Middag")
    private var didAutoGuessDishType = false
    private var sharedURL: URL?

    private func debugDumpIncomingAttachments(context: String) {
#if !DEBUG
        return
#else
        guard let extensionItems = extensionContext?.inputItems as? [NSExtensionItem] else {
            self.debugNotice("[DEBUG] attachments(\(context)) none: inputItems not NSExtensionItem")
            return
        }

        var totalProviders = 0
        for item in extensionItems {
            guard let attachments = item.attachments else { continue }
            for provider in attachments {
                totalProviders += 1
                let utis = provider.registeredTypeIdentifiers.joined(separator: ", ")
                self.debugNotice("[DEBUG] attachments(\(context)) UTIs: \(utis)")

                // Quick signal flags (cheap checks only).
                let hasURL = provider.hasItemConformingToTypeIdentifier(UTType.url.identifier)
                    || provider.hasItemConformingToTypeIdentifier(UTType.fileURL.identifier)
                    || provider.canLoadObject(ofClass: URL.self)
                let hasImage = provider.canLoadObject(ofClass: UIImage.self)
                    || provider.registeredTypeIdentifiers.contains(where: { UTType($0)?.conforms(to: .image) == true })
                let hasMovie = provider.registeredTypeIdentifiers.contains(where: { UTType($0)?.conforms(to: .movie) == true })
                    || provider.registeredTypeIdentifiers.contains(where: { UTType($0)?.conforms(to: .video) == true })
                if hasURL || hasImage || hasMovie {
                    self.debugNotice("[DEBUG] attachments(\(context)) flags: url=\(hasURL) image=\(hasImage) movie=\(hasMovie)")
                }
            }
        }

        self.debugNotice("[DEBUG] attachments(\(context)) providers=\(totalProviders)")
#endif
    }

    private func debugNotice(_ message: String) {
#if DEBUG
        // Console.app on macOS sometimes hides unified logs from extensions depending on
        // device settings/filtering. NSLog is a reliable fallback when debugging.
        shareLogger.notice("\(message, privacy: .public)")
        NSLog("%{public}@", message)
#endif
    }

    private func debugDumpPasteboard(context: String) {
#if !DEBUG
        return
#else
        let pb = UIPasteboard.general
        self.debugNotice(
            "[DEBUG] pasteboard(\(context)) hasStrings=\(pb.hasStrings) hasURLs=\(pb.hasURLs) hasImages=\(pb.hasImages) numberOfItems=\(pb.numberOfItems)"
        )

        if let s = pb.string {
            let trimmed = s.trimmingCharacters(in: .whitespacesAndNewlines)
            let oneLine = trimmed.replacingOccurrences(of: "\n", with: " ")
            let snippet = oneLine.count > 180 ? String(oneLine.prefix(180)) + "…" : oneLine
            self.debugNotice("[DEBUG] pasteboard(\(context)) pb.string len=\(trimmed.count) snippet=\(snippet)")
        }

        // Log the advertised UTIs in the pasteboard items (best-effort, limit output).
        if let first = pb.items.first {
            let keys = first.keys.sorted().prefix(12).joined(separator: ", ")
            self.debugNotice("[DEBUG] pasteboard(\(context)) firstItemTypes: \(keys)")
        }

        // iOS can also surface pasteboard content via item providers.
        if #available(iOS 11.0, *) {
            let providers = pb.itemProviders
            self.debugNotice("[DEBUG] pasteboard(\(context)) itemProviders=\(providers.count)")
            if let p0 = providers.first {
                let utis = p0.registeredTypeIdentifiers.prefix(16).joined(separator: ", ")
                self.debugNotice("[DEBUG] pasteboard(\(context)) provider0 UTIs: \(utis)")
            }
        }
#endif
    }

    private func pasteboardTextCandidate() -> String? {
        let pb = UIPasteboard.general

        if let s = pb.string {
            let t = s.trimmingCharacters(in: .whitespacesAndNewlines)
            if !t.isEmpty { return t }
        }

        // Prefer explicit plain-text representations if present.
        if let first = pb.items.first {
            let preferredKeys = [
                UTType.utf8PlainText.identifier,
                UTType.plainText.identifier,
                UTType.text.identifier,
            ]
            for k in preferredKeys {
                if let v = first[k] {
                    if let s = v as? String {
                        let t = s.trimmingCharacters(in: .whitespacesAndNewlines)
                        if !t.isEmpty { return t }
                    }
                    if let data = v as? Data {
                        if let s = String(data: data, encoding: .utf8) {
                            let t = s.trimmingCharacters(in: .whitespacesAndNewlines)
                            if !t.isEmpty { return t }
                        }
                        if let s = String(data: data, encoding: .utf16) {
                            let t = s.trimmingCharacters(in: .whitespacesAndNewlines)
                            if !t.isEmpty { return t }
                        }
                    }
                }
            }

            // If we have HTML, convert to plain text via NSAttributedString.
            if let v = first[UTType.html.identifier] {
                let html: String?
                if let s = v as? String { html = s }
                else if let data = v as? Data { html = String(data: data, encoding: .utf8) ?? String(data: data, encoding: .utf16) }
                else { html = nil }

                if let html, !html.isEmpty {
                    if let data = html.data(using: .utf8),
                       let att = try? NSAttributedString(
                        data: data,
                        options: [
                            .documentType: NSAttributedString.DocumentType.html,
                            .characterEncoding: String.Encoding.utf8.rawValue,
                        ],
                        documentAttributes: nil
                       )
                    {
                        let t = att.string.trimmingCharacters(in: .whitespacesAndNewlines)
                        if !t.isEmpty { return t }
                    }
                }
            }

            // Last resort: any string-like value.
            for (_, v) in first {
                if let s = v as? String {
                    let t = s.trimmingCharacters(in: .whitespacesAndNewlines)
                    if !t.isEmpty { return t }
                }
            }
        }

        return nil
    }

    private func fetchInstagramPreview(from url: URL, completion: @escaping (InstagramPreview?) -> Void) {
        // Best-effort: fetch HTML and parse OpenGraph/meta tags. This runs on-device (user IP),
        // which can behave differently than server-side scraping.
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.timeoutInterval = 12
        request.setValue("text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", forHTTPHeaderField: "Accept")
        request.setValue("sv-SE,sv;q=0.9,en-US;q=0.8,en;q=0.7", forHTTPHeaderField: "Accept-Language")
        // iOS Safari-ish UA to reduce bot-style responses.
        request.setValue(
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
            forHTTPHeaderField: "User-Agent"
        )

        let config = URLSessionConfiguration.ephemeral
        config.waitsForConnectivity = false
        let session = URLSession(configuration: config)

        session.dataTask(with: request) { [weak self] data, response, error in
            guard let self else { return }
            if let error {
                self.debugNotice("[DEBUG] IG preview fetch failed: \(String(describing: error))")
                completion(nil)
                return
            }

            guard let http = response as? HTTPURLResponse else {
                self.debugNotice("[DEBUG] IG preview fetch: no HTTPURLResponse")
                completion(nil)
                return
            }

            let status = http.statusCode
            self.debugNotice("[DEBUG] IG preview fetch HTTP \(status)")
            guard (200...299).contains(status), let data else {
                completion(nil)
                return
            }

            // Decode best-effort.
            let html = String(data: data, encoding: .utf8) ?? String(data: data, encoding: .isoLatin1)
            guard let html else {
                self.debugNotice("[DEBUG] IG preview fetch: could not decode HTML")
                completion(nil)
                return
            }

            let preview = self.parseInstagramPreviewHTML(html, baseURL: url)
            if preview?.captionText != nil || preview?.thumbnailURL != nil {
                let capLen = preview?.captionText?.count ?? 0
                self.debugNotice("[DEBUG] IG preview parsed capLen=\(capLen) thumb=\(preview?.thumbnailURL?.absoluteString ?? "(none)")")
            } else {
                self.debugNotice("[DEBUG] IG preview parsed nothing")
            }
            completion(preview)
        }.resume()
    }

    private func fetchImage(from url: URL, completion: @escaping (UIImage?) -> Void) {
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.timeoutInterval = 12
        request.setValue("image/*,*/*;q=0.8", forHTTPHeaderField: "Accept")
        request.setValue(
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
            forHTTPHeaderField: "User-Agent"
        )

        let config = URLSessionConfiguration.ephemeral
        config.waitsForConnectivity = false
        let session = URLSession(configuration: config)

        session.dataTask(with: request) { [weak self] data, response, error in
            guard let self else { return }
            if let error {
                self.debugNotice("[DEBUG] fetchImage failed: \(String(describing: error))")
                completion(nil)
                return
            }
            guard let http = response as? HTTPURLResponse else {
                self.debugNotice("[DEBUG] fetchImage: no HTTPURLResponse")
                completion(nil)
                return
            }
            self.debugNotice("[DEBUG] fetchImage HTTP \(http.statusCode) bytes=\(data?.count ?? 0)")
            guard (200...299).contains(http.statusCode), let data else {
                completion(nil)
                return
            }
            if let image = UIImage(data: data) {
                completion(image)
            } else {
                self.debugNotice("[DEBUG] fetchImage: UIImage decode failed")
                completion(nil)
            }
        }.resume()
    }

    private func parseInstagramPreviewHTML(_ html: String, baseURL: URL) -> InstagramPreview? {
        // Very small, robust-ish meta tag extraction.
        func extractMeta(_ key: String) -> String? {
            // Matches: <meta property="og:description" content="..."> or name="description"
            // We keep it simple and case-insensitive.
            let patterns = [
                "<meta[^>]+property=\"\(key)\"[^>]+content=\"([^\"]*)\"",
                "<meta[^>]+name=\"\(key)\"[^>]+content=\"([^\"]*)\"",
                "<meta[^>]+content=\"([^\"]*)\"[^>]+property=\"\(key)\"",
                "<meta[^>]+content=\"([^\"]*)\"[^>]+name=\"\(key)\"",
            ]
            for p in patterns {
                if let r = html.range(of: p, options: [.regularExpression, .caseInsensitive]) {
                    let snippet = String(html[r])
                    if let m = snippet.range(of: "content=\"", options: [.caseInsensitive]) {
                        let rest = snippet[m.upperBound...]
                        if let end = rest.firstIndex(of: "\"") {
                            return String(rest[..<end])
                        }
                    }
                }
            }
            return nil
        }

        func htmlUnescape(_ s: String) -> String {
            var t = s
            t = t.replacingOccurrences(of: "&amp;", with: "&")
            t = t.replacingOccurrences(of: "&quot;", with: "\"")
            t = t.replacingOccurrences(of: "&#39;", with: "'")
            t = t.replacingOccurrences(of: "&lt;", with: "<")
            t = t.replacingOccurrences(of: "&gt;", with: ">")

            // Decode numeric HTML entities like &#229; or &#xE5; (incl. emojis like &#x1F31F;).
            // We keep it small and robust.
            func decodeNumericEntities(_ input: String) -> String {
                var out = input

                // Hex: &#x1F31F;
                if let reHex = try? NSRegularExpression(pattern: "&#x([0-9A-Fa-f]+);", options: []) {
                    let matches = reHex.matches(in: out, options: [], range: NSRange(out.startIndex..., in: out))
                    for m in matches.reversed() {
                        guard m.numberOfRanges == 2,
                              let r = Range(m.range(at: 0), in: out),
                              let rHex = Range(m.range(at: 1), in: out)
                        else { continue }
                        let hex = String(out[rHex])
                        if let value = UInt32(hex, radix: 16), let scalar = UnicodeScalar(value) {
                            out.replaceSubrange(r, with: String(Character(scalar)))
                        }
                    }
                }

                // Decimal: &#229;
                if let reDec = try? NSRegularExpression(pattern: "&#([0-9]+);", options: []) {
                    let matches = reDec.matches(in: out, options: [], range: NSRange(out.startIndex..., in: out))
                    for m in matches.reversed() {
                        guard m.numberOfRanges == 2,
                              let r = Range(m.range(at: 0), in: out),
                              let rDec = Range(m.range(at: 1), in: out)
                        else { continue }
                        let dec = String(out[rDec])
                        if let value = UInt32(dec, radix: 10), let scalar = UnicodeScalar(value) {
                            out.replaceSubrange(r, with: String(Character(scalar)))
                        }
                    }
                }

                return out
            }

            return decodeNumericEntities(t)
        }

        func sanitizeInstagramCaption(_ raw: String) -> String {
            var t = raw.trimmingCharacters(in: .whitespacesAndNewlines)

            // Instagram og:description often looks like:
            // "username Month DD, YYYY: \"...caption...\"." (with entities)
            // Strip the username+date prefix if present.
            if let re = try? NSRegularExpression(pattern: "^\\S+\\s+[A-Za-z]+\\s+\\d{1,2},\\s+\\d{4}:\\s+\"", options: []) {
                let r = NSRange(t.startIndex..., in: t)
                if let m = re.firstMatch(in: t, options: [], range: r),
                   let prefixRange = Range(m.range(at: 0), in: t)
                {
                    t.removeSubrange(prefixRange)
                }
            }

            // Strip surrounding quotes and a trailing period.
            if t.hasPrefix("\"") { t.removeFirst() }
            if t.hasSuffix("\".") { t = String(t.dropLast(2)) }
            if t.hasSuffix("\"") { t.removeLast() }

            return t.trimmingCharacters(in: .whitespacesAndNewlines)
        }

        let ogDescRaw = extractMeta("og:description")
        let descRaw = extractMeta("description")
        let ogImageRaw = extractMeta("og:image")

        var caption: String? = nil
        if let ogDescRaw {
            let t = sanitizeInstagramCaption(htmlUnescape(ogDescRaw))
            // Instagram often prefixes with "X likes, Y comments - ...". Keep only the trailing part.
            if let dash = t.range(of: " - ") {
                caption = String(t[dash.upperBound...]).trimmingCharacters(in: .whitespacesAndNewlines)
            } else {
                caption = t
            }
        }
        if (caption == nil || caption?.isEmpty == true), let descRaw {
            let t = sanitizeInstagramCaption(htmlUnescape(descRaw))
            caption = t
        }

        // Avoid worthless captions.
        if let c = caption, c.count < 20 {
            caption = nil
        }

        var thumbURL: URL? = nil
        if let ogImageRaw {
            let t = htmlUnescape(ogImageRaw).trimmingCharacters(in: .whitespacesAndNewlines)
            thumbURL = URL(string: t) ?? URL(string: t, relativeTo: baseURL)
        }

        if caption == nil && thumbURL == nil { return nil }
        return InstagramPreview(captionText: caption, thumbnailURL: thumbURL)
    }

    private func textWithoutURLs(_ text: String) -> String {
        // Remove URL substrings so we can tell whether the user actually provided caption text.
        // Instagram commonly shares only a URL, which otherwise prevents pasteboard-caption fallback.
        var t = text
        if let detector = try? NSDataDetector(types: NSTextCheckingResult.CheckingType.link.rawValue) {
            let range = NSRange(location: 0, length: t.utf16.count)
            let matches = detector.matches(in: t, options: [], range: range)
            for match in matches.reversed() {
                if let r = Range(match.range, in: t) {
                    t.removeSubrange(r)
                }
            }
        }
        // Normalize whitespace/newlines after removals.
        t = t
            .replacingOccurrences(of: "\r\n", with: "\n")
            .replacingOccurrences(of: "\n\n\n+", with: "\n\n", options: .regularExpression)
        return t.trimmingCharacters(in: .whitespacesAndNewlines)
    }

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
        self.debugNotice("[DEBUG] ShareViewController.viewDidLoad")
        self.debugDumpIncomingAttachments(context: "viewDidLoad")
        self.loadSharedURLIfAvailable()
    }

    override func didSelectPost() {
        // This is called after the user selects Post. Do the upload of contentText and/or NSExtensionContext attachments.

        self.debugNotice("[DEBUG] ShareViewController.didSelectPost")
        
        guard let extensionItems = extensionContext?.inputItems as? [NSExtensionItem] else {
            self.extensionContext?.completeRequest(returningItems: [], completionHandler: nil)
            return
        }

        // IMPORTANT:
        // Some apps share multiple attachments (e.g. UIImage + NSURL). The order is not stable.
        // We must prefer a real web URL if *any* attachment contains one, and only fall back to image OCR
        // when we have exhausted URL/text candidates.
        var didFinish = false
        func finishOnce(_ work: @escaping () -> Void) {
            guard !didFinish else { return }
            didFinish = true
            work()
        }

        // Flatten all providers so we can do a URL-first pass across all attachments.
        struct AttachmentCandidate {
            let provider: NSItemProvider
            let extensionItem: NSExtensionItem?
        }

        var candidates: [AttachmentCandidate] = []
        for item in extensionItems {
            guard let attachments = item.attachments else { continue }
            for provider in attachments {
                // Debug: learn what other apps share (ICA/kokaihop, etc.).
                let utis = provider.registeredTypeIdentifiers.joined(separator: ", ")
                self.debugNotice("[DEBUG] attachment UTIs: \(utis)")
                candidates.append(.init(provider: provider, extensionItem: item))
            }
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

        var preflightText = preflightTextCandidates.joined(separator: "\n\n")
        var preflightURL = preflightTextCandidates.compactMap { self.extractURL(from: $0) }.first

        let isInstagramShare: Bool = {
            guard let url = preflightURL, let host = url.host?.lowercased() else { return false }
            return host.contains("instagram.com")
        }()

        // Instagram sometimes shares only an image (no URL/text). Some apps still make this work
        // by reading a recently-copied link from pasteboard. Only touch pasteboard if needed.
        if preflightURL == nil {
            let pb = UIPasteboard.general
            if let u = pb.url {
                preflightURL = u
            } else if let s = pb.string, let u = self.extractURL(from: s) {
                preflightURL = u
            }
        }

        // Debug assist: if we didn't find a URL in preflight text/pasteboard but we do have providers,
        // dump pasteboard info anyway. Some apps provide the actual URL only through item providers.
        if preflightURL == nil, !candidates.isEmpty {
            self.debugDumpPasteboard(context: "didSelectPost-preflightURL-none")
        }

        // If this is an Instagram share, dump pasteboard metadata for debugging. Some apps rely on
        // Instagram placing an image/video on the pasteboard even when attachments are URL-only.
        if isInstagramShare {
            self.debugDumpPasteboard(context: "didSelectPost")
        }

        // Instagram often shares only the URL without caption text.
        // If the user copied the caption right before sharing, pick it up from pasteboard.
        // IMPORTANT: treat "text that is just a URL" as empty caption, otherwise this fallback never triggers.
          if let url = preflightURL,
              let host = url.host?.lowercased(),
              host.contains("instagram.com")
        {
            let captionCandidate = self.textWithoutURLs(preflightText)
            if captionCandidate.isEmpty {
                let pb = UIPasteboard.general
                if let s = pb.string {
                    let trimmed = s.trimmingCharacters(in: .whitespacesAndNewlines)
                    if !trimmed.isEmpty,
                       self.extractURL(from: trimmed) == nil,
                       Self.looksLikeInstagramCaption(trimmed)
                    {
                        preflightText = trimmed
                        self.debugNotice("[DEBUG] Using pasteboard caption text for Instagram (len=\(preflightText.count))")
                    } else {
                        self.debugNotice("[DEBUG] Pasteboard caption not used for Instagram (pbLen=\(trimmed.count))")
                    }
                } else {
                    self.debugNotice("[DEBUG] Pasteboard has no string for Instagram")
                }
            }
        }

        // Same rationale: `.notice` is easier to capture from devices.
        self.debugNotice(
            "[DEBUG] preflightTextLen=\(preflightText.count) preflightURL=\(preflightURL?.absoluteString ?? "(none)") candidates=\(candidates.count)"
        )

        let hasPotentialImage = candidates.contains { c in
            c.provider.canLoadObject(ofClass: UIImage.self) || c.provider.registeredTypeIdentifiers.contains(where: { UTType($0)?.conforms(to: .image) == true })
        }

        // Instagram: prefer image import (thumbnail) + caption parsing, if we have an image.
        if
            let url = preflightURL,
            let host = url.host?.lowercased(),
            host.contains("instagram.com"),
            hasPotentialImage
        {
            self.debugNotice("[DEBUG] Instagram URL detected; will prefer image import if image is available.")
            tryUploadImageFromCandidatesWithContext(0, sourceURL: url, sourceText: preflightText)
            return
        }

        // Instagram sometimes shares only a URL attachment, but places an image on the pasteboard.
        // If so, import that image (thumbnail) instead of attempting server-side scraping.
        if
            let url = preflightURL,
            let host = url.host?.lowercased(),
            host.contains("instagram.com"),
            !hasPotentialImage
        {
            let pb = UIPasteboard.general
            if pb.hasImages, let image = pb.image ?? pb.images?.first {
                self.debugNotice("[DEBUG] Instagram URL detected; using pasteboard image for import.")
                let inferredTitle = self.bestEffortTitleForImageImport(suggestedName: nil, item: nil)
                finishOnce { self.uploadImage(image, title: inferredTitle, sourceURL: url, sourceText: preflightText) }
                return
            }
        }

        // Default: if we already found a URL, use it.
        if let url = preflightURL {
            self.debugNotice("[DEBUG] Found URL in preflight text (len=\(preflightText.count)).")
            finishOnce { self.uploadURL(url, sourceText: preflightText) }
            return
        }

        func tryUploadImageFromCandidatesWithContext(_ idx: Int, sourceURL: URL?, sourceText: String?) {
            if didFinish { return }
            guard idx < candidates.count else {
                DispatchQueue.main.async {
                    if let url = self.extractURL(from: self.contentText) {
                        finishOnce { self.uploadURL(url, sourceText: sourceText ?? self.contentText) }
                    } else {
                        self.showEphemeralNoticeAndComplete(message: "Ingen länk hittades")
                    }
                }
                return
            }

            let provider = candidates[idx].provider
            let suggestedName = provider.suggestedName
            let registeredTypeIdentifiers = provider.registeredTypeIdentifiers

            if provider.canLoadObject(ofClass: UIImage.self) {
                _ = provider.loadObject(ofClass: UIImage.self) { [weak self] object, error in
                    guard let self else { return }
                    if didFinish { return }
                    if let error {
                        shareLogger.error("Failed to load UIImage object: \(String(describing: error), privacy: .public)")
                        tryUploadImageFromCandidatesWithContext(idx + 1, sourceURL: sourceURL, sourceText: sourceText)
                        return
                    }
                    if let image = object as? UIImage {
                        let inferredTitle = self.bestEffortTitleForImageImport(
                            suggestedName: suggestedName,
                            item: nil
                        )
                        finishOnce { self.uploadImage(image, title: inferredTitle, sourceURL: sourceURL, sourceText: sourceText) }
                    } else {
                        tryUploadImageFromCandidatesWithContext(idx + 1, sourceURL: sourceURL, sourceText: sourceText)
                    }
                }
                return
            }

            for typeId in registeredTypeIdentifiers {
                guard let ut = UTType(typeId), ut.conforms(to: .image) else { continue }
                provider.loadItem(forTypeIdentifier: typeId) { [weak self] item, error in
                    guard let self else { return }
                    if didFinish { return }
                    if let error {
                        shareLogger.error("Failed to load image item (\(typeId, privacy: .public)): \(String(describing: error), privacy: .public)")
                        tryUploadImageFromCandidatesWithContext(idx + 1, sourceURL: sourceURL, sourceText: sourceText)
                        return
                    }
                    if let image = item as? UIImage {
                        let inferredTitle = self.bestEffortTitleForImageImport(suggestedName: suggestedName, item: item)
                        finishOnce { self.uploadImage(image, title: inferredTitle, sourceURL: sourceURL, sourceText: sourceText) }
                        return
                    }
                    if let url = item as? URL, url.isFileURL, let data = try? Data(contentsOf: url), let image = UIImage(data: data) {
                        let inferredTitle = self.bestEffortTitleForImageImport(suggestedName: suggestedName, item: url)
                        finishOnce { self.uploadImage(image, title: inferredTitle, sourceURL: sourceURL, sourceText: sourceText) }
                        return
                    }
                    if let data = item as? Data, let image = UIImage(data: data) {
                        let inferredTitle = self.bestEffortTitleForImageImport(suggestedName: suggestedName, item: item)
                        finishOnce { self.uploadImage(image, title: inferredTitle, sourceURL: sourceURL, sourceText: sourceText) }
                        return
                    }
                    tryUploadImageFromCandidatesWithContext(idx + 1, sourceURL: sourceURL, sourceText: sourceText)
                }
                return
            }

            tryUploadImageFromCandidatesWithContext(idx + 1, sourceURL: sourceURL, sourceText: sourceText)
        }

        func tryUploadImageFromCandidates(_ idx: Int) {
            if didFinish { return }
            guard idx < candidates.count else {
                DispatchQueue.main.async {
                    if let url = self.extractURL(from: self.contentText) {
                        finishOnce { self.uploadURL(url, sourceText: self.contentText) }
                    } else {
                        self.showEphemeralNoticeAndComplete(message: "Ingen länk hittades")
                    }
                }
                return
            }

            let provider = candidates[idx].provider
            let suggestedName = provider.suggestedName
            let registeredTypeIdentifiers = provider.registeredTypeIdentifiers

            // Prefer direct UIImage loading.
            if provider.canLoadObject(ofClass: UIImage.self) {
                _ = provider.loadObject(ofClass: UIImage.self) { [weak self] object, error in
                    guard let self else { return }
                    if didFinish { return }

                    if let error {
                        shareLogger.error("Failed to load UIImage object: \(String(describing: error), privacy: .public)")
                        tryUploadImageFromCandidates(idx + 1)
                        return
                    }
                    if let image = object as? UIImage {
                        let inferredTitle = self.bestEffortTitleForImageImport(
                            suggestedName: suggestedName,
                            item: nil
                        )
                        finishOnce { self.uploadImage(image, title: inferredTitle) }
                    } else {
                        tryUploadImageFromCandidates(idx + 1)
                    }
                }
                return
            }

            // As a fallback, try to load image data if it conforms to UTType.image.
            for typeId in registeredTypeIdentifiers {
                guard let ut = UTType(typeId), ut.conforms(to: .image) else { continue }
                provider.loadItem(forTypeIdentifier: typeId) { [weak self] item, error in
                    guard let self else { return }
                    if didFinish { return }

                    if let error {
                        shareLogger.error("Failed to load image item (\(typeId, privacy: .public)): \(String(describing: error), privacy: .public)")
                        tryUploadImageFromCandidates(idx + 1)
                        return
                    }

                    if let image = item as? UIImage {
                        let inferredTitle = self.bestEffortTitleForImageImport(
                            suggestedName: suggestedName,
                            item: item
                        )
                        finishOnce { self.uploadImage(image, title: inferredTitle) }
                        return
                    }
                    if let url = item as? URL, url.isFileURL, let data = try? Data(contentsOf: url), let image = UIImage(data: data) {
                        let inferredTitle = self.bestEffortTitleForImageImport(
                            suggestedName: suggestedName,
                            item: url
                        )
                        finishOnce { self.uploadImage(image, title: inferredTitle) }
                        return
                    }
                    if let data = item as? Data, let image = UIImage(data: data) {
                        let inferredTitle = self.bestEffortTitleForImageImport(
                            suggestedName: suggestedName,
                            item: item
                        )
                        finishOnce { self.uploadImage(image, title: inferredTitle) }
                        return
                    }

                    tryUploadImageFromCandidates(idx + 1)
                }
                return
            }

            tryUploadImageFromCandidates(idx + 1)
        }

        func tryUploadURLFromCandidates(_ idx: Int) {
            if didFinish { return }
            guard idx < candidates.count else {
                // No URL found anywhere -> try pasteboard one last time before falling back to images.
                let pb = UIPasteboard.general
                let pbURL = pb.url ?? (pb.string.flatMap { self.extractURL(from: $0) })
                if let url = pbURL {
                    finishOnce { self.uploadURL(url, sourceText: preflightText) }
                } else {
                    tryUploadImageFromCandidates(0)
                }
                return
            }

            let provider = candidates[idx].provider

            // Prefer explicit URL UTIs to avoid the "try NSURL for public.image" problem.
            let urlTypeIdentifiers: [String] = [
                UTType.url.identifier,
                UTType.fileURL.identifier,
            ]

            for typeId in urlTypeIdentifiers where provider.hasItemConformingToTypeIdentifier(typeId) {
                provider.loadItem(forTypeIdentifier: typeId) { [weak self] (item, error) in
                    guard let self else { return }
                    if didFinish { return }

                    if let error {
                        shareLogger.error("Failed to load URL item (\(typeId, privacy: .public)): \(String(describing: error), privacy: .public)")
                        tryUploadURLFromCandidates(idx + 1)
                        return
                    }

                    let itemType = item.map { String(describing: type(of: $0)) } ?? "(nil)"
                    self.debugNotice("[DEBUG] URL item loaded type=\(itemType) uti=\(typeId)")

                    if let url = self.extractURL(fromItem: item) ?? self.extractURL(from: self.contentText) {
                        self.debugNotice("[DEBUG] URL extracted: \(url.absoluteString)")

                        // If URL is Instagram and share text is empty (often only URL is shared),
                        // attempt to capture caption-like text from pasteboard, then from an on-device HTML fetch.
                        var sourceTextToSend = preflightText
                        if let host = url.host?.lowercased(), host.contains("instagram.com") {
                            let captionCandidate = self.textWithoutURLs(sourceTextToSend)
                            if captionCandidate.isEmpty {
                                if let pbText = self.pasteboardTextCandidate() {
                                    let pbTrimmed = pbText.trimmingCharacters(in: .whitespacesAndNewlines)
                                    if !pbTrimmed.isEmpty,
                                       self.extractURL(from: pbTrimmed) == nil,
                                       Self.looksLikeInstagramCaption(pbTrimmed)
                                    {
                                        sourceTextToSend = pbTrimmed
                                        self.debugNotice("[DEBUG] Using pasteboard text for Instagram source_text (len=\(pbTrimmed.count))")
                                    } else {
                                        let snippetOneLine = pbTrimmed.replacingOccurrences(of: "\n", with: " ")
                                        let snippet = snippetOneLine.count > 160 ? String(snippetOneLine.prefix(160)) + "…" : snippetOneLine
                                        self.debugNotice("[DEBUG] Pasteboard text not accepted as caption (len=\(pbTrimmed.count)) snippet=\(snippet)")
                                    }
                                } else {
                                    self.debugNotice("[DEBUG] No pasteboard text candidate for Instagram")
                                }

                                // If still empty, try fetching on-device preview HTML (may contain og:description).
                                let finalCandidate = self.textWithoutURLs(sourceTextToSend)
                                if finalCandidate.isEmpty {
                                    self.debugNotice("[DEBUG] IG source_text still empty; fetching IG preview HTML")
                                    self.fetchInstagramPreview(from: url) { preview in
                                        if didFinish { return }

                                        let caption = (preview?.captionText?.trimmingCharacters(in: .whitespacesAndNewlines)).flatMap { $0.isEmpty ? nil : $0 }
                                        let thumbnailURL = preview?.thumbnailURL

                                        // Prefer creating via image import so we get a thumbnail saved on the recipe,
                                        // while still allowing the backend to parse caption text into ingredients/steps.
                                        if let thumbnailURL {
                                            self.debugNotice("[DEBUG] IG preview has thumbnail; downloading and using image import")
                                            self.fetchImage(from: thumbnailURL) { image in
                                                if didFinish { return }
                                                if let image {
                                                    let inferredTitle = self.bestEffortTitleForImageImport(suggestedName: nil, item: nil)
                                                    finishOnce { self.uploadImage(image, title: inferredTitle, sourceURL: url, sourceText: caption) }
                                                } else {
                                                    self.debugNotice("[DEBUG] IG thumbnail download failed; falling back to URL import")
                                                    finishOnce { self.uploadURL(url, sourceText: caption ?? sourceTextToSend) }
                                                }
                                            }
                                            return
                                        }

                                        // No thumbnail -> fall back to URL import with caption text.
                                        finishOnce { self.uploadURL(url, sourceText: caption ?? sourceTextToSend) }
                                    }
                                    return
                                }
                            }
                        }

                        finishOnce { self.uploadURL(url, sourceText: sourceTextToSend) }
                    } else {
                        let textSnippet = self.coerceText(from: item).map { s in
                            let t = s.replacingOccurrences(of: "\n", with: " ")
                            return t.count > 140 ? String(t.prefix(140)) + "…" : t
                        } ?? "(no text)"
                        self.debugNotice("[DEBUG] URL extraction failed for uti=\(typeId); textSnippet=\(textSnippet)")
                        // Try URL object loading as an immediate fallback for this provider.
                        if provider.canLoadObject(ofClass: URL.self) {
                            _ = provider.loadObject(ofClass: URL.self) { [weak self] object, error in
                                guard let self else { return }
                                if didFinish { return }

                                if error != nil {
                                    tryUploadURLFromCandidates(idx + 1)
                                    return
                                }
                                if let url = object {
                                    self.debugNotice("[DEBUG] URL extracted via loadObject: \(url.absoluteString)")
                                    finishOnce { self.uploadURL(url, sourceText: preflightText) }
                                } else {
                                    tryUploadURLFromCandidates(idx + 1)
                                }
                            }
                        } else {
                            tryUploadURLFromCandidates(idx + 1)
                        }
                    }
                }
                return
            }

            // Text-like UTIs
            let textTypeIdentifiers = [
                UTType.plainText.identifier,
                UTType.utf8PlainText.identifier,
                UTType.text.identifier,
                UTType.html.identifier,
                UTType.rtf.identifier,
                UTType.rtfd.identifier,
            ]

            for typeId in textTypeIdentifiers where provider.hasItemConformingToTypeIdentifier(typeId) {
                provider.loadItem(forTypeIdentifier: typeId) { [weak self] (item, error) in
                    guard let self else { return }
                    if didFinish { return }

                    if let error {
                        shareLogger.error("Failed to load text item (\(typeId, privacy: .public)): \(String(describing: error), privacy: .public)")
                        tryUploadURLFromCandidates(idx + 1)
                        return
                    }

                    if let url = self.extractURL(fromItem: item) ?? self.extractURL(from: self.contentText) {
                        finishOnce { self.uploadURL(url, sourceText: preflightText) }
                    } else {
                        tryUploadURLFromCandidates(idx + 1)
                    }
                }
                return
            }

            // Data-like UTIs: some apps (incl. Instagram) may embed a URL inside a property list / JSON blob.
            let dataTypeIdentifiers = [
                UTType.propertyList.identifier,
                UTType.json.identifier,
                UTType.data.identifier,
                UTType.item.identifier,
            ]

            for typeId in dataTypeIdentifiers where provider.hasItemConformingToTypeIdentifier(typeId) {
                provider.loadItem(forTypeIdentifier: typeId) { [weak self] (item, error) in
                    guard let self else { return }
                    if didFinish { return }

                    if let error {
                        shareLogger.error("Failed to load data item (\(typeId, privacy: .public)): \(String(describing: error), privacy: .public)")
                        tryUploadURLFromCandidates(idx + 1)
                        return
                    }

                    if let url = self.extractURL(fromItem: item) ?? self.extractURL(from: self.contentText) {
                        finishOnce { self.uploadURL(url, sourceText: preflightText) }
                    } else {
                        tryUploadURLFromCandidates(idx + 1)
                    }
                }
                return
            }

            // Brute-force: try any remaining non-image UTIs and attempt URL extraction from the payload.
            // Some providers don't correctly advertise URL/text UTIs even if they embed a URL.
            let excluded = Set(urlTypeIdentifiers + textTypeIdentifiers + dataTypeIdentifiers)
            var otherTypeIdentifiers = provider.registeredTypeIdentifiers
                .filter { !excluded.contains($0) }
                .filter { UTType($0)?.conforms(to: .image) != true }

            if otherTypeIdentifiers.count > 12 {
                otherTypeIdentifiers = Array(otherTypeIdentifiers.prefix(12))
            }

            if !otherTypeIdentifiers.isEmpty {
                func tryOtherType(_ tIdx: Int) {
                    if didFinish { return }
                    guard tIdx < otherTypeIdentifiers.count else {
                        tryUploadURLFromCandidates(idx + 1)
                        return
                    }

                    let typeId = otherTypeIdentifiers[tIdx]
                    provider.loadItem(forTypeIdentifier: typeId) { [weak self] (item, error) in
                        guard let self else { return }
                        if didFinish { return }

                        if error != nil {
                            tryOtherType(tIdx + 1)
                            return
                        }

                        if let url = self.extractURL(fromItem: item) ?? self.extractURL(from: self.contentText) {
                            finishOnce { self.uploadURL(url, sourceText: preflightText) }
                        } else {
                            tryOtherType(tIdx + 1)
                        }
                    }
                }

                tryOtherType(0)
                return
            }

            // Some providers still expose URL objects without advertising URL UTIs reliably.
            // Only try this as a last resort for this provider.
            if provider.canLoadObject(ofClass: URL.self) {
                _ = provider.loadObject(ofClass: URL.self) { [weak self] object, error in
                    guard let self else { return }
                    if didFinish { return }

                    if let error {
                        shareLogger.error("Failed to load URL object: \(String(describing: error), privacy: .public)")
                        tryUploadURLFromCandidates(idx + 1)
                        return
                    }
                    if let url = object {
                        finishOnce { self.uploadURL(url, sourceText: preflightText) }
                    } else {
                        tryUploadURLFromCandidates(idx + 1)
                    }
                }
                return
            }

            // Continue scanning
            tryUploadURLFromCandidates(idx + 1)
        }

        // Start URL-first scanning.
        tryUploadURLFromCandidates(0)
        return
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
            shareLogger.info("[DEBUG] API_BASE_URL raw: \(raw, privacy: .public)")
            // Normalize base URL so it points to the API root (ends with /api/).
            // This avoids accidentally hitting the web UI and receiving HTML redirects.
            func collapseSlashes(_ input: String) -> String {
                // Collapse consecutive slashes in path-like strings.
                // Note: URLs may contain "//" after scheme; we only use this for paths.
                var s = input
                while s.contains("//") {
                    s = s.replacingOccurrences(of: "//", with: "/")
                }
                return s
            }

            var components = URLComponents(url: url, resolvingAgainstBaseURL: false)
            var path = components?.path ?? url.path
            path = collapseSlashes(path)

            // Ensure path ends with /api/
            if path.hasSuffix("/api") {
                path = path + "/"
            } else if !path.hasSuffix("/api/") {
                path = (path.hasSuffix("/") ? path : path + "/") + "api/"
            }

            path = collapseSlashes(path)
            components?.path = path
            components?.query = nil
            components?.fragment = nil
            if let normalized = components?.url {
                return normalized
            }
            // Fallback: best-effort
            return URL(string: (components?.string ?? raw)) ?? url
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

        // NSItemProvider often returns bridged Foundation classes.
        if let nsurl = item as? NSURL {
            return nsurl as URL
        }
        if let nsstr = item as? NSString {
            return extractURL(from: nsstr as String)
        }

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
        if let s = item as? NSString {
            return s as String
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
    
    private func uploadURL(_ url: URL, sourceText: String?) {
        shareLogger.info("Attempting import for shared URL: \(url.absoluteString, privacy: .public)")
        // IMPORTANT: build the path with components to avoid encoding slashes ("recipes/import/")
        // and to ensure trailing slash (Django APPEND_SLASH redirects can break POST semantics).
        var apiUrl = apiBaseURL
            .appendingPathComponent("recipes", isDirectory: true)
            .appendingPathComponent("import", isDirectory: true)

        // Some servers treat double slashes as distinct paths -> 404.
        if var c = URLComponents(url: apiUrl, resolvingAgainstBaseURL: false) {
            while c.path.contains("//") {
                c.path = c.path.replacingOccurrences(of: "//", with: "/")
            }
            apiUrl = c.url ?? apiUrl
        }
        shareLogger.info("[DEBUG] uploadURL endpoint: \(apiUrl.absoluteString, privacy: .public)")
        
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
        
        var body: [String: Any] = [
            "url": url.absoluteString,
            "dish_type": selectedDishType.id,
        ]
        let trimmedSource = (sourceText ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        if !trimmedSource.isEmpty {
            body["source_text"] = trimmedSource
        }
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
                        // Keep log size reasonable.
                        let snippet = body.count > 800 ? String(body.prefix(800)) + "…" : body
                        shareLogger.error("Import failed body: \(snippet, privacy: .public)")
                    }

                    shareLogger.error("Import failed with HTTP \(httpResponse.statusCode) at \(apiUrl.absoluteString, privacy: .public)")

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

    private func bestEffortTitleForImageImport(suggestedName: String?, item: Any?) -> String {
        func sanitize(_ raw: String) -> String {
            var s = Self.stripAfterPipe(raw)
                .trimmingCharacters(in: .whitespacesAndNewlines)

            // Avoid generic app names as titles.
            let lowered = s
                .folding(options: [.diacriticInsensitive, .caseInsensitive], locale: .current)
                .lowercased()
            if lowered == "instagram" || lowered == "reels" {
                return ""
            }

            // If the share sheet text includes multiple lines (common when apps share "everything"),
            // only keep the first non-empty line as the title.
            let lines = s
                .replacingOccurrences(of: "\r\n", with: "\n")
                .split(separator: "\n", omittingEmptySubsequences: true)
                .map { String($0).trimmingCharacters(in: .whitespacesAndNewlines) }
                .filter { !$0.isEmpty }

            if let first = lines.first {
                s = first
            }

            // Cut off common section markers that shouldn't be part of the title.
            let lowered2 = s
                .folding(options: [.diacriticInsensitive, .caseInsensitive], locale: .current)
                .lowercased()
            let markers = ["ingredienser", "gor sa har", "gör sa här", "gör så här", "instruktioner", "tillagning"]
            for m in markers {
                if let r = lowered2.range(of: m) {
                    let idx = s.index(s.startIndex, offsetBy: lowered2.distance(from: lowered2.startIndex, to: r.lowerBound))
                    s = String(s[..<idx]).trimmingCharacters(in: .whitespacesAndNewlines)
                    break
                }
            }

            // Avoid sending a URL as the "title".
            if let url = URL(string: s), url.scheme != nil, url.host != nil {
                return ""
            }

            // Keep it reasonably small (backend will also cap to 200).
            if s.count > 120 {
                s = String(s.prefix(120)).trimmingCharacters(in: .whitespacesAndNewlines)
            }
            return s
        }

        // 1) Whatever the user sees/typed in the share sheet
        let primary = sanitize(self.textView.text ?? self.contentText)
        if !primary.isEmpty { return primary }

        // 2) Some apps populate the extension item's title
        if let items = extensionContext?.inputItems as? [NSExtensionItem] {
            if let t = items.compactMap({ $0.attributedTitle?.string }).first(where: { !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }) {
                let cleaned = sanitize(t)
                if !cleaned.isEmpty { return cleaned }
            }
        }

        // 3) Provider suggested filename/title
        if let name = suggestedName?.trimmingCharacters(in: .whitespacesAndNewlines), !name.isEmpty {
            let cleaned = name.replacingOccurrences(of: "_", with: " ")
            let s = sanitize(cleaned)
            if !s.isEmpty { return s }
        }

        // 4) If the item is a file URL, use the filename (without extension)
        if let url = item as? URL, url.isFileURL {
            let base = url.deletingPathExtension().lastPathComponent
            let s = sanitize(base)
            if !s.isEmpty { return s }
        }

        return ""
    }

    private enum ImageUpload {
        case jpeg(Data)
        case png(Data)

        var data: Data {
            switch self {
            case .jpeg(let d): return d
            case .png(let d): return d
            }
        }

        var contentType: String {
            switch self {
            case .jpeg: return "image/jpeg"
            case .png: return "image/png"
            }
        }

        var filename: String {
            switch self {
            case .jpeg: return "share.jpg"
            case .png: return "share.png"
            }
        }
    }

    private func uploadImage(_ image: UIImage, title: String, sourceURL: URL? = nil, sourceText: String? = nil) {
        let pixelWidth = Int(image.size.width * image.scale)
        let pixelHeight = Int(image.size.height * image.scale)
        shareLogger.info("Shared image size: \(pixelWidth)x\(pixelHeight)px (scale=\(image.scale))")

        // Heuristic: some apps (incl. Kokaihop) sometimes share a tiny thumbnail/app-icon image.
        // OCR on those is pointless and just creates noisy placeholder recipes.
        if min(pixelWidth, pixelHeight) > 0 && min(pixelWidth, pixelHeight) < 320 {
            DispatchQueue.main.async {
                self.showEphemeralNoticeAndComplete(
                    message: "Kokaihop delade bara en liten bild (ingen recepttext). Ta en skärmdump med ingredienser/steg och dela den, eller dela länken från webben."
                )
            }
            return
        }

        // Prefer PNG (lossless) for text screenshots when reasonably sized.
        let payload: ImageUpload?
        if let png = image.pngData(), png.count <= 8_000_000 {
            payload = .png(png)
        } else if let jpeg = image.jpegData(compressionQuality: 0.95) {
            payload = .jpeg(jpeg)
        } else {
            payload = nil
        }

        guard let payload else {
            self.showEphemeralNoticeAndComplete(message: "Kunde inte läsa bild")
            return
        }

        let titleForImageImport = title.trimmingCharacters(in: .whitespacesAndNewlines)

        var apiUrl = apiBaseURL
            .appendingPathComponent("recipes", isDirectory: true)
            .appendingPathComponent("import-image", isDirectory: true)

        if var c = URLComponents(url: apiUrl, resolvingAgainstBaseURL: false) {
            while c.path.contains("//") {
                c.path = c.path.replacingOccurrences(of: "//", with: "/")
            }
            apiUrl = c.url ?? apiUrl
        }
        shareLogger.info("[DEBUG] uploadImage endpoint: \(apiUrl.absoluteString, privacy: .public)")
        self.debugNotice("[DEBUG] uploadImage endpoint: \(apiUrl.absoluteString)")
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

        if !titleForImageImport.isEmpty {
            append("--\(boundary)\r\n")
            append("Content-Disposition: form-data; name=\"title\"\r\n\r\n")
            append("\(titleForImageImport)\r\n")
        }

        if let sourceURL {
            append("--\(boundary)\r\n")
            append("Content-Disposition: form-data; name=\"source_url\"\r\n\r\n")
            append("\(sourceURL.absoluteString)\r\n")
        }

        if let sourceText, !sourceText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            append("--\(boundary)\r\n")
            append("Content-Disposition: form-data; name=\"source_text\"\r\n\r\n")
            append("\(sourceText)\r\n")
        }

        append("--\(boundary)\r\n")
        append("Content-Disposition: form-data; name=\"image\"; filename=\"\(payload.filename)\"\r\n")
        append("Content-Type: \(payload.contentType)\r\n\r\n")
        body.append(payload.data)
        append("\r\n")
        append("--\(boundary)--\r\n")

        request.httpBody = body

        shareLogger.info("Attempting import from shared image (bytes=\(payload.data.count))")
        self.debugNotice("[DEBUG] uploadImage starting bytes=\(payload.data.count) sourceTextLen=\((sourceText ?? "").count)")

        let task = URLSession.shared.dataTask(with: request) { [weak self] data, response, error in
            guard let self else { return }

            if let error {
                shareLogger.error("Image upload error: \(String(describing: error), privacy: .public)")
                self.debugNotice("[DEBUG] uploadImage error: \(String(describing: error))")
                DispatchQueue.main.async {
                    self.showEphemeralNoticeAndComplete(message: "Kunde inte spara")
                }
                return
            }

            if let http = response as? HTTPURLResponse {
                shareLogger.info("Image upload HTTP status: \(http.statusCode)")
                self.debugNotice("[DEBUG] uploadImage HTTP \(http.statusCode)")
                if http.statusCode == 201 || http.statusCode == 200 {
                    DispatchQueue.main.async {
                        self.showEphemeralNoticeAndComplete(message: "Sparad till MinaRecept")
                    }
                } else {
                    if let data, let body = String(data: data, encoding: .utf8) {
                        shareLogger.error("Image import failed body: \(body, privacy: .public)")
                        let snippet = body.count > 600 ? String(body.prefix(600)) + "…" : body
                        self.debugNotice("[DEBUG] uploadImage failed body: \(snippet)")
                    }
                    DispatchQueue.main.async {
                        self.showEphemeralNoticeAndComplete(message: "Kunde inte spara")
                    }
                }
                return
            }

            DispatchQueue.main.async {
                self.debugNotice("[DEBUG] uploadImage: no HTTP response")
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

    private static func looksLikeInstagramCaption(_ text: String) -> Bool {
        let t = text.trimmingCharacters(in: .whitespacesAndNewlines)
        if t.count < 40 { return false }

        let lower = t.lowercased()
        let hasSwedishMarkers = lower.contains("ingredien") || lower.contains("gör så här") || lower.contains("gör såhär")
        let hasEnglishMarkers = lower.contains("ingredients") || lower.contains("instructions") || lower.contains("method")
        if hasSwedishMarkers || hasEnglishMarkers { return true }

        // Fallback: multi-line + list-like formatting.
        let lineCount = t.split(separator: "\n").count
        if lineCount >= 5 && (t.contains("- ") || t.contains("•") || t.contains("1.")) {
            return true
        }
        return false
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
