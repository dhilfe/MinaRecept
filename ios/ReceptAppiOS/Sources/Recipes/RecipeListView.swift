import SwiftUI

struct RecipeListView: View {
    @EnvironmentObject private var session: SessionController
    @Environment(\.openURL) private var openURL

    let resetToken: Int

    @State private var recipes: [RecipeDTO] = []
    @State private var cookbooks: [CookbookDTO] = []
    @State private var isLoading: Bool = false
    @State private var errorMessage: String? = nil
    @State private var searchText: String = ""
    @State private var selectedCategory: String? = nil
    @State private var path = NavigationPath()
    @State private var showCreateSheet: Bool = false

    @State private var showCreateCookbookPrompt: Bool = false
    @State private var newCookbookName: String = ""
    @State private var isCreatingCookbook: Bool = false

    @State private var selectedTags: Set<String> = []

    @FocusState private var isSearchFocused: Bool

    private enum TopSection: String, CaseIterable, Identifiable {
        case myRecipes = "Mina recept"
        case inspiration = "Inspiration"
        case following = "Följer"

        var id: String { rawValue }
    }

    private enum CollectionSegment: String, CaseIterable, Identifiable {
        case saved = "Sparade"
        case liked = "Gillade"
        case shared = "Delade"

        var id: String { rawValue }
    }

    @State private var topSection: TopSection = .myRecipes
    @State private var collectionSegment: CollectionSegment = .saved
    @State private var showFilters: Bool = false

    private func performHomeReset() {
        path = NavigationPath()
        searchText = ""
        selectedCategory = nil
        selectedTags = []
        showFilters = false
        isSearchFocused = false
    }

    private func searchTokens(from rawQuery: String) -> [String] {
        let cleaned = rawQuery
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .replacingOccurrences(of: "#", with: " ")

        return cleaned
            .split(whereSeparator: { $0 == "," || $0.isWhitespace })
            .map { String($0).trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
    }

    private func tagsList(for recipe: RecipeDTO) -> [String] {
        guard let tags = recipe.tags, !tags.isEmpty else { return [] }
        return tags
            .split(separator: ",")
            .map { String($0).trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
    }

    private var searchedRecipes: [RecipeDTO] {
        let tokens = searchTokens(from: searchText)
        guard !tokens.isEmpty else { return recipes }

        return recipes.filter { recipe in
            let recipeTags = tagsList(for: recipe)
            return tokens.allSatisfy { token in
                if recipe.title.localizedCaseInsensitiveContains(token) {
                    return true
                }
                return recipeTags.contains(where: { $0.localizedCaseInsensitiveContains(token) })
            }
        }
    }

    private var tagFilteredRecipes: [RecipeDTO] {
        guard !selectedTags.isEmpty else { return searchedRecipes }
        let selected = selectedTags.map { $0.lowercased() }

        return searchedRecipes.filter { recipe in
            let recipeTags = Set(tagsList(for: recipe).map { $0.lowercased() })
            return selected.allSatisfy { recipeTags.contains($0) }
        }
    }

    private var filteredRecipes: [RecipeDTO] {
        guard let selectedCategory else { return searchedRecipes }
        return tagFilteredRecipes.filter { categoryName(for: $0) == selectedCategory }
    }

    private var displayedRecipes: [RecipeDTO] {
        filteredRecipes
            .sorted { $0.title.localizedCaseInsensitiveCompare($1.title) == .orderedAscending }
    }

    private var availableTags: [String] {
        var seen = Set<String>()
        var out: [String] = []

        for recipe in searchedRecipes {
            for tag in tagsList(for: recipe) {
                let cleaned = tag.trimmingCharacters(in: .whitespacesAndNewlines)
                guard !cleaned.isEmpty else { continue }
                let key = cleaned.lowercased()
                guard !seen.contains(key) else { continue }
                seen.insert(key)
                out.append(cleaned)
            }
        }

        out.sort { $0.localizedCaseInsensitiveCompare($1) == .orderedAscending }
        return out
    }

    private struct RecipeRow: View {
        let recipe: RecipeDTO
        let tags: [String]

        var body: some View {
            HStack(alignment: .top, spacing: 12) {
                if let url = recipe.preferredImageURL {
                    AsyncImage(url: url) { image in
                        image
                            .resizable()
                            .scaledToFill()
                    } placeholder: {
                        RoundedRectangle(cornerRadius: 12)
                            .fill(Color.secondary.opacity(0.15))
                    }
                    .frame(width: 64, height: 64)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                    .overlay {
                        RoundedRectangle(cornerRadius: 12)
                            .strokeBorder(.secondary.opacity(0.15))
                    }
                } else {
                    RoundedRectangle(cornerRadius: 12)
                        .fill(Color.secondary.opacity(0.10))
                        .frame(width: 64, height: 64)
                        .overlay {
                            Image(systemName: "fork.knife")
                                .foregroundStyle(.secondary)
                        }
                }

                VStack(alignment: .leading, spacing: 6) {
                    Text(recipe.title)
                        .font(.headline)
                        .foregroundStyle(.primary)
                        .lineLimit(2)

                    if !tags.isEmpty {
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 6) {
                                ForEach(tags.prefix(6), id: \.self) { tag in
                                    Text(tag)
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                        .padding(.horizontal, 10)
                                        .padding(.vertical, 4)
                                        .background(.thinMaterial)
                                        .clipShape(Capsule())
                                }
                            }
                        }
                    }
                }

                Spacer(minLength: 0)
            }
            .padding(.vertical, 2)
        }
    }

    private struct CookbookCard: View {
        let title: String
        let imageURLs: [URL]

        var body: some View {
            VStack(alignment: .leading, spacing: 10) {
                RoundedRectangle(cornerRadius: 14)
                    .fill(Color.secondary.opacity(0.10))
                    .overlay {
                        HStack(spacing: 0) {
                            ForEach(Array(imageURLs.prefix(3).enumerated()), id: \.offset) { _, url in
                                AsyncImage(url: url) { image in
                                    image.resizable().scaledToFill()
                                } placeholder: {
                                    Color.secondary.opacity(0.15)
                                }
                            }
                        }
                        .clipped()
                    }
                    .frame(width: 120, height: 88)
                    .clipShape(RoundedRectangle(cornerRadius: 14))
                    .overlay {
                        RoundedRectangle(cornerRadius: 14)
                            .strokeBorder(.secondary.opacity(0.15))
                    }

                Text(title)
                    .font(.headline)
                    .foregroundStyle(.primary)
                    .lineLimit(1)
            }
        }
    }

    private struct CreateCookbookCard: View {
        var body: some View {
            VStack(alignment: .leading, spacing: 10) {
                RoundedRectangle(cornerRadius: 14)
                    .fill(Color.secondary.opacity(0.10))
                    .overlay {
                        Image(systemName: "plus")
                            .font(.system(size: 22, weight: .semibold))
                            .foregroundStyle(.secondary)
                    }
                    .frame(width: 120, height: 88)
                    .clipShape(RoundedRectangle(cornerRadius: 14))
                    .overlay {
                        RoundedRectangle(cornerRadius: 14)
                            .strokeBorder(.secondary.opacity(0.15))
                    }

                Text("Skapa")
                    .font(.headline)
                    .foregroundStyle(.primary)
                    .lineLimit(1)
            }
        }
    }

    private var categoryNames: [String] {
        let names = Set(searchedRecipes.map { categoryName(for: $0) })
        return names.sorted(by: compareCategoryNames(_:_:))
    }

    private func compareCategoryNames(_ a: String, _ b: String) -> Bool {
        if a == "Lunch/Middag" && b != "Lunch/Middag" { return true }
        if b == "Lunch/Middag" && a != "Lunch/Middag" { return false }
        return a.localizedCaseInsensitiveCompare(b) == .orderedAscending
    }

    var body: some View {
        NavigationStack(path: $path) {
            List {
                Section {
                    Picker("", selection: $topSection) {
                        ForEach(TopSection.allCases) { section in
                            Text(section.rawValue).tag(section)
                        }
                    }
                    .pickerStyle(.segmented)
                }
                .listRowInsets(EdgeInsets(top: 8, leading: 16, bottom: 0, trailing: 16))

                if topSection == .myRecipes {
                    Section("Dina kokböcker") {
                        let urls = recipes.compactMap { $0.preferredImageURL }
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 14) {
                                Button {
                                    // Users expect this to always show their recipes.
                                    topSection = .myRecipes
                                    collectionSegment = .saved
                                    searchText = ""
                                    selectedCategory = nil
                                    selectedTags = []
                                    showFilters = false
                                    isSearchFocused = false
                                } label: {
                                    CookbookCard(title: "Alla recept", imageURLs: urls)
                                }
                                .buttonStyle(.plain)

                                ForEach(cookbooks) { cookbook in
                                    Button {
                                        path.append(cookbook)
                                    } label: {
                                        CookbookCard(title: cookbook.name, imageURLs: cookbook.previewImageURLs ?? [])
                                    }
                                    .buttonStyle(.plain)
                                }

                                Button {
                                    showCreateCookbookPrompt = true
                                } label: {
                                    CreateCookbookCard()
                                }
                                .buttonStyle(.plain)
                            }
                            .padding(.vertical, 4)
                        }
                    }

                    Section {
                        Picker("", selection: $collectionSegment) {
                            ForEach(CollectionSegment.allCases) { segment in
                                Text(segment.rawValue).tag(segment)
                            }
                        }
                        .pickerStyle(.segmented)
                    }
                    .listRowInsets(EdgeInsets(top: 0, leading: 16, bottom: 0, trailing: 16))

                    Section {
                        HStack(spacing: 10) {
                            Image(systemName: "magnifyingglass")
                                .foregroundStyle(.secondary)
                            TextField("Sök recept…", text: $searchText)
                                .textInputAutocapitalization(.never)
                                .autocorrectionDisabled(true)
                                .focused($isSearchFocused)

                            Button {
                                showFilters.toggle()
                            } label: {
                                Image(systemName: "slider.horizontal.3")
                                    .foregroundStyle(.secondary)
                            }
                            .buttonStyle(.plain)
                        }
                        .padding(.horizontal, 12)
                        .padding(.vertical, 10)
                        .background(Color.secondary.opacity(0.10))
                        .clipShape(RoundedRectangle(cornerRadius: 14))

                        if showFilters {
                            categoryFilterBar
                            tagFilterBar
                        }
                    }
                    .listRowInsets(EdgeInsets(top: 6, leading: 16, bottom: 6, trailing: 16))

                    if collectionSegment != .saved {
                        Section {
                            Text("Kommer snart")
                                .foregroundStyle(.secondary)
                        }
                    }

                    if recipes.isEmpty && !isLoading && searchText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                        Section {
                            EmptyStateView(
                                iconName: "fork.knife",
                                title: "Inga recept än",
                                message: "Spara dina favoritrecept från webben genom att dela dem till MinaRecept.",
                                actionTitle: nil,
                                action: nil
                            )
                        }
                    } else if searchedRecipes.isEmpty {
                        Section {
                            if searchText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                                Text("Inga recept hittades.")
                                    .foregroundStyle(.secondary)
                            } else {
                                Text("Inga recept matchar \"\(searchText)\".")
                                    .foregroundStyle(.secondary)
                                Button("Sök på Google efter \"\(searchText)\"") {
                                    openGoogleSearch(query: searchText)
                                }
                            }
                        }
                    } else if displayedRecipes.isEmpty {
                        Section {
                            Text("Inga recept i vald kategori.")
                                .foregroundStyle(.secondary)
                        }
                    } else {
                        Section {
                            ForEach(displayedRecipes) { recipe in
                                NavigationLink(value: recipe) {
                                    RecipeRow(recipe: recipe, tags: tagsList(for: recipe))
                                }
                            }
                            .onDelete { offsets in
                                deleteRecipes(in: displayedRecipes, at: offsets)
                            }
                        }

                        if !searchText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                            Section {
                                Button("Sök på Google efter \"\(searchText)\"") {
                                    openGoogleSearch(query: searchText)
                                }
                            } header: {
                                Text("Hittade du inte det du sökte?")
                            }
                        }
                    }
                } else {
                    Section {
                        Text("Kommer snart")
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .navigationTitle("Hem")
            .listStyle(.insetGrouped)
            .navigationDestination(for: RecipeDTO.self) { recipe in
                RecipeDetailView(recipe: recipe)
            }
            .navigationDestination(for: CookbookDTO.self) { cookbook in
                CookbookRecipesView(cookbook: cookbook)
                    .environmentObject(session)
            }
            .toolbar {
                ToolbarItemGroup(placement: .topBarTrailing) {
                    Button {
                        showCreateSheet = true
                    } label: {
                        Image(systemName: "plus")
                    }

                    Menu {
                        Button("Logga ut", role: .destructive) { session.logout() }
                    } label: {
                        Image(systemName: "ellipsis.circle")
                    }
                }

                if isLoading {
                    ToolbarItem(placement: .topBarLeading) {
                        ProgressView()
                    }
                }
            }
            .sheet(isPresented: $showCreateSheet) {
                RecipeCreateView { created in
                    recipes.append(created)
                    session.triggerReloadRecipes()
                    path.append(created)
                }
                .environmentObject(session)
            }
            .overlay {
                if isLoading && recipes.isEmpty {
                    ProgressView("Laddar recept...")
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
            .alert("Ge din nya kokbok ett namn", isPresented: $showCreateCookbookPrompt) {
                TextField("Namn", text: $newCookbookName)
                Button("Avbryt", role: .cancel) { }
                Button("Lägg till") {
                    Task { await createCookbook() }
                }
            }
            .background(
                TabReselectDetector { _ in
                    performHomeReset()
                }
                .frame(width: 0, height: 0)
            )
            .onChange(of: resetToken) { _ in
                performHomeReset()
            }
            .onChange(of: topSection) { _ in
                isSearchFocused = false
            }
            .onChange(of: searchText) { _ in
                if let selectedCategory, !categoryNames.contains(selectedCategory) {
                    self.selectedCategory = nil
                }
            }
            .task(id: session.reloadRecipesSignal) { await loadRecipes() }
            .refreshable {
                await loadRecipes()
            }
        }
    }

    @ViewBuilder
    private var categoryFilterBar: some View {
        if !categoryNames.isEmpty {
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    Group {
                        if selectedCategory == nil {
                            Button("Alla") {
                                selectedCategory = nil
                            }
                            .buttonStyle(.borderedProminent)
                        } else {
                            Button("Alla") {
                                selectedCategory = nil
                            }
                            .buttonStyle(.bordered)
                        }
                    }

                    ForEach(categoryNames, id: \.self) { category in
                        Group {
                            if selectedCategory == category {
                                Button(category) {
                                    selectedCategory = category
                                }
                                .buttonStyle(.borderedProminent)
                            } else {
                                Button(category) {
                                    selectedCategory = category
                                }
                                .buttonStyle(.bordered)
                            }
                        }
                    }
                }
                .padding(.horizontal)
                .padding(.vertical, 8)
            }
        }
    }

    @ViewBuilder
    private var tagFilterBar: some View {
        if !availableTags.isEmpty {
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    Group {
                        if selectedTags.isEmpty {
                            Button("Alla taggar") {
                                selectedTags = []
                            }
                            .buttonStyle(.borderedProminent)
                        } else {
                            Button("Alla taggar") {
                                selectedTags = []
                            }
                            .buttonStyle(.bordered)
                        }
                    }

                    ForEach(availableTags, id: \.self) { tag in
                        let key = tag.lowercased()
                        Group {
                            if selectedTags.contains(key) {
                                Button("#\(tag)") {
                                    selectedTags.remove(key)
                                }
                                .buttonStyle(.borderedProminent)
                            } else {
                                Button("#\(tag)") {
                                    selectedTags.insert(key)
                                }
                                .buttonStyle(.bordered)
                            }
                        }
                    }
                }
                .padding(.horizontal)
                .padding(.vertical, 8)
            }
        }
    }

    private func categoryName(for recipe: RecipeDTO) -> String {
        if !recipe.dishTypeDisplayName.isEmpty {
            return recipe.dishTypeDisplayName
        }
        return "Okategoriserat"
    }

    private func openGoogleSearch(query: String) {
        let trimmed = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }

        var components = URLComponents(string: "https://www.google.com/search")
        components?.queryItems = [URLQueryItem(name: "q", value: "recept \(trimmed)")]
        guard let url = components?.url else { return }
        openURL(url)
    }

    private func loadRecipes() async {
        guard let token = session.token else { return }
        if isLoading { return }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            recipes = try await APIClient.shared.fetchRecipes(token: token)
            cookbooks = try await APIClient.shared.fetchCookbooks(token: token)
        } catch {
            errorMessage = APIError.userFacingMessage(for: error)
        }
    }

    @MainActor
    private func createCookbook() async {
        guard let token = session.token else { return }
        let trimmed = newCookbookName.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            errorMessage = "Namnet kan inte vara tomt."
            return
        }
        guard !isCreatingCookbook else { return }

        isCreatingCookbook = true
        errorMessage = nil
        defer { isCreatingCookbook = false }

        do {
            _ = try await APIClient.shared.createCookbook(name: trimmed, token: token)
            newCookbookName = ""
            cookbooks = try await APIClient.shared.fetchCookbooks(token: token)
        } catch {
            errorMessage = "Kunde inte skapa kokbok. \(APIError.userFacingMessage(for: error))"
        }
    }

    private func deleteRecipes(in sectionRecipes: [RecipeDTO], at offsets: IndexSet) {
        guard let token = session.token else { return }

        let recipesToDelete = offsets.map { sectionRecipes[$0] }

        let idsToDelete = Set(recipesToDelete.map { $0.id })
        recipes.removeAll { idsToDelete.contains($0.id) }

        Task {
            for recipe in recipesToDelete {
                do {
                    try await APIClient.shared.deleteRecipe(id: recipe.id, token: token)
                } catch {
                    errorMessage = APIError.userFacingMessage(for: error)
                    await loadRecipes()
                }
            }
        }
    }
}
