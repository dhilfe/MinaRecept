import SwiftUI

struct RecipeDetailView: View {
    @EnvironmentObject private var session: SessionController

    private enum DetailTab: String, CaseIterable {
        case cook = "Tillaga"
        case comments = "Kommentarer"
        case film = "Se film"
    }

    @State private var recipe: RecipeDTO
    @State private var isLoading: Bool = false
    @State private var errorMessage: String? = nil
    @State private var showSuccessAlert = false
    @State private var showEditSheet = false
    @State private var checkedIngredientIds: Set<String> = []
    @State private var checkedStepKeys: Set<String> = []
    @State private var selectedTab: DetailTab = .cook
    @State private var servings: Int = 4
    @State private var baseServings: Int = 4
    @State private var showCookbookSheet: Bool = false

    init(recipe: RecipeDTO) {
        _recipe = State(initialValue: recipe)
        let initialServings = max(1, recipe.servings ?? 4)
        _servings = State(initialValue: initialServings)
        _baseServings = State(initialValue: initialServings)
    }

    private var parsedSteps: [String] { parseSteps(recipe.steps) }
    private var parsedIngredients: [IngredientDTO] { IngredientsParser.parse(recipe.ingredients) }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                headerSection
                tabsSection

                switch selectedTab {
                case .cook:
                    cookTab
                case .comments:
                    placeholderTab(text: "Kommer snart")
                case .film:
                    placeholderTab(text: "Kommer snart")
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
        }
        .navigationTitle("Recept")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button {
                    showEditSheet = true
                } label: {
                    Image(systemName: "pencil")
                }
                    .disabled(isLoading)
            }

            if isLoading {
                ToolbarItem(placement: .topBarTrailing) {
                    ProgressView()
                }
            }
        }
        .sheet(isPresented: $showEditSheet) {
            RecipeEditView(recipe: recipe) { updated in
                // Update local detail + ask list views to refresh.
                recipe = updated
                session.triggerReloadRecipes()
            }
            .environmentObject(session)
        }
        .safeAreaInset(edge: .bottom) {
            if let errorMessage {
                Text(errorMessage)
                    .frame(maxWidth: .infinity)
                    .padding(12)
                    .background(.thinMaterial)
            }
        }
        .task {
            await loadRecipe()
        }
        .alert("Tillagt", isPresented: $showSuccessAlert) {
            Button("OK", role: .cancel) { }
        } message: {
            Text("Ingredienserna har lagts till i din inköpslista.")
        }
        .sheet(isPresented: $showCookbookSheet) {
            if let token = session.token {
                CookbookPickerSheet(recipeId: recipe.id, token: token)
            } else {
                EmptyStateView(
                    iconName: "book",
                    title: "Du har inga kokböcker än",
                    message: "Logga in för att skapa kokböcker."
                )
            }
        }
        .onChange(of: recipe.servings) { newValue in
            guard let newValue else { return }
            if servings == baseServings {
                servings = max(1, newValue)
            }
            baseServings = max(1, newValue)
        }
        .refreshable {
            await loadRecipe()
        }
    }

    private var headerSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(recipe.title)
                .font(.title)
                .fontWeight(.semibold)

            if let originalUrl = parseOriginalSource(from: recipe.description).originalUrl {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Originalreceptet är från")
                        .foregroundStyle(.secondary)
                    Link(sourceLabel(for: originalUrl), destination: originalUrl)
                        .foregroundStyle(.secondary)
                }
            }

            HStack(spacing: 12) {
                Circle()
                    .fill(.orange)
                    .frame(width: 44, height: 44)
                    .overlay(
                        Text("D")
                            .foregroundStyle(.white)
                            .fontWeight(.bold)
                    )
                Text("Du")
                    .font(.headline)
                Spacer(minLength: 0)
            }

            actionButtons
        }
    }

    private var actionButtons: some View {
        VStack(spacing: 10) {
            PillButton(title: "Lägg till i kokbok", systemImage: "book") {
                showCookbookSheet = true
            }

            HStack(spacing: 10) {
                PillButton(title: "Lägg till i\ninköpslista", systemImage: "basket") {
                    Task { await addToShoppingList() }
                }
                .disabled(isLoading)

                ShareLink(item: shareText) {
                    pillLabel(title: "Dela", systemImage: "square.and.arrow.up")
                }
            }
        }
    }

    private func pillLabel(title: String, systemImage: String) -> some View {
        HStack(spacing: 10) {
            Image(systemName: systemImage)
            Text(title)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 14)
        .padding(.horizontal, 12)
        .background(.thinMaterial)
        .clipShape(Capsule())
    }

    private var tabsSection: some View {
        HStack(spacing: 0) {
            ForEach(DetailTab.allCases, id: \.self) { tab in
                Button {
                    selectedTab = tab
                } label: {
                    VStack(spacing: 8) {
                        Text(tab.rawValue)
                            .font(.headline)
                            .foregroundStyle(selectedTab == tab ? .primary : .secondary)
                        Rectangle()
                            .fill(selectedTab == tab ? Color.primary : Color.clear)
                            .frame(height: 2)
                    }
                    .frame(maxWidth: .infinity)
                }
                .buttonStyle(.plain)
            }
        }
    }

    private func placeholderTab(text: String) -> some View {
        Text(text)
            .foregroundStyle(.secondary)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.top, 12)
    }

    private var cookTab: some View {
        VStack(alignment: .leading, spacing: 16) {
            servingsControl
            cookModeButton
            ingredientsBlock
            stepsBlock
            missingContentBlock
        }
    }

    private var servingsControl: some View {
        HStack(spacing: 12) {
            Button {
                servings = max(1, servings - 1)
            } label: {
                Image(systemName: "minus")
                    .frame(width: 44, height: 44)
            }
            .buttonStyle(.bordered)

            Text("För \(servings) portioner")
                .font(.headline)
                .frame(maxWidth: .infinity)

            Button {
                servings = min(99, servings + 1)
            } label: {
                Image(systemName: "plus")
                    .frame(width: 44, height: 44)
            }
            .buttonStyle(.bordered)
        }
    }

    @ViewBuilder
    private var cookModeButton: some View {
        if !parsedSteps.isEmpty {
            NavigationLink {
                CookModeView(title: recipe.title, steps: parsedSteps)
            } label: {
                Text("Öppna i matlagningsvy")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
        }
    }

    @ViewBuilder
    private var ingredientsBlock: some View {
        if !parsedIngredients.isEmpty {
            VStack(alignment: .leading, spacing: 12) {
                Text("\(parsedIngredients.count) Ingredienser")
                    .font(.title2)
                    .fontWeight(.bold)

                let all = parsedIngredients
                ForEach(Array(all.enumerated()), id: \.element.id) { idx, ing in
                    let text = formatIngredient(ing)
                    let nextText: String? = {
                        guard idx + 1 < all.count else { return nil }
                        return formatIngredient(all[idx + 1])
                    }()

                    if isHeadingLine(ing: ing, text: text, nextText: nextText) {
                        Text(normalizeTrailingColon(text))
                            .font(.title3)
                            .fontWeight(.semibold)
                            .padding(.top, 6)
                    } else {
                        ingredientRow(ing: ing, text: normalizeTrailingColon(text))
                    }
                }
            }
        }
    }

    private func ingredientRow(ing: IngredientDTO, text: String) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 12) {
            Button {
                if checkedIngredientIds.contains(ing.id) {
                    checkedIngredientIds.remove(ing.id)
                } else {
                    checkedIngredientIds.insert(ing.id)
                }
            } label: {
                Image(systemName: checkedIngredientIds.contains(ing.id) ? "checkmark.square" : "square")
                    .foregroundStyle(checkedIngredientIds.contains(ing.id) ? .green : .secondary)
            }
            .buttonStyle(.plain)

            Text(text)
                .foregroundStyle(.primary)
                .frame(maxWidth: .infinity, alignment: .leading)

            Button {
                Task { await addSingleIngredientToShoppingList(text: text) }
            } label: {
                Image(systemName: "cart.badge.plus")
                    .foregroundStyle(.secondary)
            }
            .buttonStyle(.plain)
            .disabled(isLoading)
        }
        .padding(.vertical, 6)
    }

    private func addSingleIngredientToShoppingList(text: String) async {
        guard let token = session.token else { return }
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }

        isLoading = true
        defer { isLoading = false }

        do {
            try await APIClient.shared.addSingleIngredientToShoppingList(
                recipeId: recipe.id,
                text: trimmed,
                shoppingListId: nil,
                token: token
            )
            showSuccessAlert = true
        } catch {
            errorMessage = APIError.userFacingMessage(for: error)
        }
    }

    @ViewBuilder
    private var stepsBlock: some View {
        if !parsedSteps.isEmpty {
            VStack(alignment: .leading, spacing: 12) {
                Text("Gör så här")
                    .font(.title2)
                    .fontWeight(.bold)

                ForEach(Array(parsedSteps.enumerated()), id: \.offset) { idx, step in
                    let key = "\(idx)|\(step)"
                    if isHeadingStep(step) {
                        Text(step.trimmingCharacters(in: .whitespacesAndNewlines).trimmingCharacters(in: CharacterSet(charactersIn: ":")))
                            .font(.title3)
                            .fontWeight(.semibold)
                            .padding(.top, 6)
                    } else {
                        Button {
                            if checkedStepKeys.contains(key) {
                                checkedStepKeys.remove(key)
                            } else {
                                checkedStepKeys.insert(key)
                            }
                        } label: {
                            HStack(alignment: .top, spacing: 12) {
                                Image(systemName: checkedStepKeys.contains(key) ? "checkmark.square" : "square")
                                      .foregroundStyle(checkedStepKeys.contains(key) ? .green : .secondary)
                                    .padding(.top, 2)
                                Text(step)
                                    .foregroundStyle(.primary)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                            }
                        }
                        .buttonStyle(.plain)
                        .padding(.vertical, 6)
                    }
                }
            }
        }
    }

    @ViewBuilder
    private var missingContentBlock: some View {
        let hasDescription = !parseOriginalSource(from: recipe.description)
            .prefixText
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .isEmpty

        if !hasDescription, parsedIngredients.isEmpty, parsedSteps.isEmpty {
            Text("Det här receptet saknar ingredienser eller steg.")
                .foregroundStyle(.secondary)
        }
    }

    private func isHeadingLine(ing: IngredientDTO, text: String, nextText: String?) -> Bool {
        let s = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard s.hasSuffix(":") else { return false }

        // If multiple consecutive lines end with ":", assume it's not intended as headings.
        if let nextText {
            let next = nextText.trimmingCharacters(in: .whitespacesAndNewlines)
            if next.hasSuffix(":") { return false }
        }

        return true
    }

    private func normalizeTrailingColon(_ text: String) -> String {
        text
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .trimmingCharacters(in: CharacterSet(charactersIn: ":"))
    }
    private func isHeadingStep(_ step: String) -> Bool {
        let s = step.trimmingCharacters(in: .whitespacesAndNewlines)
        if s.hasSuffix(":") { return true }
        // Allow simple headings like "Dressing" / "Sallad" in steps too
        if s.rangeOfCharacter(from: .decimalDigits) == nil, s.count <= 30, !s.contains(".") {
            return true
        }
        return false
    }

    private struct PillButton: View {
        let title: String
        let systemImage: String
        let action: () -> Void

        var body: some View {
            Button(action: action) {
                HStack(spacing: 10) {
                    Image(systemName: systemImage)
                    Text(title)
                        .multilineTextAlignment(.center)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 14)
                .padding(.horizontal, 12)
                .background(.thinMaterial)
                .clipShape(Capsule())
            }
            .buttonStyle(.plain)
        }
    }

    private func formatIngredient(_ ing: IngredientDTO) -> String {
        let parts = [ing.amount, ing.unit, ing.name]
            .compactMap { $0?.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
        return parts.joined(separator: " ")
    }

    private func parseSteps(_ raw: String?) -> [String] {
        let normalized = (raw ?? "")
            .replacingOccurrences(of: "\r\n", with: "\n")
            .replacingOccurrences(of: "\r", with: "\n")

        let byLines = normalized
            .split(separator: "\n")
            .map { String($0).trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }

        if byLines.count > 1 {
            return byLines
        }

        var bySentences: [String] = []
        normalized.enumerateSubstrings(
            in: normalized.startIndex..<normalized.endIndex,
            options: [.bySentences]
        ) { substring, _, _, _ in
            if let substring {
                let trimmed = substring.trimmingCharacters(in: .whitespacesAndNewlines)
                if !trimmed.isEmpty {
                    bySentences.append(trimmed)
                }
            }
        }

        if bySentences.count > 1 {
            return bySentences
        }

        return byLines
    }

    private func loadRecipe() async {
        guard let token = session.token else { return }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            recipe = try await APIClient.shared.fetchRecipe(id: recipe.id, token: token)
        } catch {
            errorMessage = APIError.userFacingMessage(for: error)
        }
    }

    private func addToShoppingList() async {
        guard let token = session.token else { return }
        isLoading = true
        defer { isLoading = false }
        
        do {
            try await APIClient.shared.addIngredientsToShoppingList(recipeId: recipe.id, shoppingListId: nil, token: token)
            showSuccessAlert = true
        } catch {
            errorMessage = APIError.userFacingMessage(for: error)
        }
    }

    private var shareText: String {
        var parts: [String] = [recipe.title]
        let parsed = parseOriginalSource(from: recipe.description)
        if !parsed.prefixText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            parts.append(parsed.prefixText.trimmingCharacters(in: .whitespacesAndNewlines))
        }
        if let url = parsed.originalUrl {
            parts.append(url.absoluteString)
        }
        return parts.joined(separator: "\n\n")
    }

    private func parseOriginalSource(from description: String?) -> (prefixText: String, originalUrl: URL?) {
        let text = description ?? ""

        // Backend appends a final line: "Originalreceptet är från <url>"
        let lines = text.split(whereSeparator: \.isNewline).map { String($0) }
        guard let lastLine = lines.last else {
            return (text, nil)
        }

        let pattern = "(?i)^\\s*originalreceptet är från\\s+(https?://\\S+)\\s*$"
        guard let regex = try? NSRegularExpression(pattern: pattern) else {
            return (text, nil)
        }

        let range = NSRange(location: 0, length: (lastLine as NSString).length)
        guard let match = regex.firstMatch(in: lastLine, range: range), match.numberOfRanges >= 2 else {
            return (text, nil)
        }

        let urlRange = match.range(at: 1)
        guard let swiftRange = Range(urlRange, in: lastLine) else {
            return (text, nil)
        }

        let urlString = String(lastLine[swiftRange])
        guard let url = URL(string: urlString) else {
            return (text, nil)
        }

        let prefix = lines.dropLast().joined(separator: "\n")
        return (prefix, url)
    }

    private func sourceLabel(for url: URL) -> String {
        if let host = url.host?.lowercased(), host.contains("instagram.com") {
            return "www.instagram.com"
        }
        return url.host ?? url.absoluteString
    }
}

private struct CookbookPickerSheet: View {
    @Environment(\.dismiss) private var dismiss

    let recipeId: Int
    let token: String

    @State private var cookbooks: [CookbookDTO] = []
    @State private var isLoading: Bool = false
    @State private var errorMessage: String? = nil

    @State private var showCreatePrompt: Bool = false
    @State private var newCookbookName: String = ""

    var body: some View {
        NavigationStack {
            Group {
                if isLoading {
                    ProgressView()
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if cookbooks.isEmpty {
                    EmptyStateView(
                        iconName: "book",
                        title: "Du har inga kokböcker än",
                        message: "",
                        actionTitle: "+ Skapa kokbok",
                        action: { showCreatePrompt = true }
                    )
                } else {
                    List {
                        ForEach(cookbooks) { cb in
                            Button {
                                Task { await addRecipe(to: cb.id) }
                            } label: {
                                HStack {
                                    Text(cb.name)
                                        .foregroundStyle(.primary)
                                    Spacer()
                                    if let count = cb.recipeCount {
                                        Text("\(count)")
                                            .foregroundStyle(.secondary)
                                    }
                                }
                            }
                            .disabled(isLoading)
                        }
                    }
                }
            }
            .navigationTitle("Kokbok")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Avbryt") { dismiss() }
                        .disabled(isLoading)
                }

                ToolbarItem(placement: .primaryAction) {
                    Button {
                        showCreatePrompt = true
                    } label: {
                        Image(systemName: "plus")
                    }
                    .disabled(isLoading)
                }
            }
            .safeAreaInset(edge: .bottom) {
                if let errorMessage {
                    Text(errorMessage)
                        .frame(maxWidth: .infinity)
                        .padding(12)
                        .background(.thinMaterial)
                }
            }
            .task {
                await loadCookbooks()
            }
            .alert("Ge din nya kokbok ett namn", isPresented: $showCreatePrompt) {
                TextField("Namn", text: $newCookbookName)
                Button("Avbryt", role: .cancel) { }
                Button("Lägg till") {
                    Task { await createCookbookAndAddRecipe() }
                }
            }
        }
    }

    @MainActor
    private func loadCookbooks() async {
        guard !isLoading else { return }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            cookbooks = try await APIClient.shared.fetchCookbooks(token: token)
        } catch {
            errorMessage = "Kunde inte hämta kokböcker. \(APIError.userFacingMessage(for: error))"
        }
    }

    @MainActor
    private func createCookbookAndAddRecipe() async {
        let trimmed = newCookbookName.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            errorMessage = "Namnet kan inte vara tomt."
            return
        }

        guard !isLoading else { return }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        let created: CookbookDTO
        do {
            created = try await APIClient.shared.createCookbook(name: trimmed, token: token)
        } catch {
            errorMessage = "Kunde inte skapa kokbok. \(APIError.userFacingMessage(for: error))"
            return
        }

        do {
            try await APIClient.shared.addRecipeToCookbook(
                cookbookId: created.id,
                recipeId: recipeId,
                token: token
            )
            dismiss()
        } catch {
            errorMessage = "Kokbok skapad men kunde inte lägga till receptet. \(APIError.userFacingMessage(for: error))"
            await loadCookbooks()
        }
    }

    @MainActor
    private func addRecipe(to cookbookId: Int) async {
        guard !isLoading else { return }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            try await APIClient.shared.addRecipeToCookbook(
                cookbookId: cookbookId,
                recipeId: recipeId,
                token: token
            )
            dismiss()
        } catch {
            errorMessage = "Kunde inte lägga till receptet i kokboken. \(APIError.userFacingMessage(for: error))"
        }
    }
}
