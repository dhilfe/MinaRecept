import SwiftUI

struct RecipeListView: View {
    @EnvironmentObject private var session: SessionController
    @Environment(\.openURL) private var openURL
    @Environment(\.dismissSearch) private var dismissSearch

    let resetToken: Int

    @State private var recipes: [RecipeDTO] = []
    @State private var isLoading: Bool = false
    @State private var errorMessage: String? = nil
    @State private var searchText: String = ""
    @State private var selectedCategory: String? = nil
    @State private var path = NavigationPath()
    @State private var showCreateSheet: Bool = false

    private func performHomeReset() {
        path = NavigationPath()
        searchText = ""
        selectedCategory = nil
        dismissSearch()
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

    private var filteredRecipes: [RecipeDTO] {
        guard let selectedCategory else { return searchedRecipes }
        return searchedRecipes.filter { categoryName(for: $0) == selectedCategory }
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
            VStack(spacing: 0) {
                categoryFilterBar

                if recipes.isEmpty && !isLoading && searchText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                    EmptyStateView(
                        iconName: "fork.knife",
                        title: "Inga recept än",
                        message: "Spara dina favoritrecept från webben genom att dela dem till MinaRecept.",
                        actionTitle: nil,
                        action: nil
                    )
                } else {
                    List {
                        if searchedRecipes.isEmpty {
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
                        } else if filteredRecipes.isEmpty {
                            Section {
                                Text("Inga recept i vald kategori.")
                                    .foregroundStyle(.secondary)
                            }
                        } else {
                            ForEach(sectionCategoryNames, id: \.self) { category in
                                Section(category) {
                                    let sectionRecipes = filteredRecipes
                                        .filter { categoryName(for: $0) == category }
                                        .sorted { $0.title.localizedCaseInsensitiveCompare($1.title) == .orderedAscending }

                                    ForEach(sectionRecipes) { recipe in
                                        NavigationLink(value: recipe) {
                                            HStack(spacing: 12) {
                                                if let url = recipe.preferredImageURL {
                                                    AsyncImage(url: url) { image in
                                                        image
                                                            .resizable()
                                                            .scaledToFill()
                                                    } placeholder: {
                                                        Color.secondary.opacity(0.2)
                                                    }
                                                    .frame(width: 56, height: 56)
                                                    .clipShape(RoundedRectangle(cornerRadius: 8))
                                                }

                                                VStack(alignment: .leading) {
                                                    Text(recipe.title)
                                                        .font(.headline)
                                                }
                                            }
                                        }
                                    }
                                    .onDelete { offsets in
                                        deleteRecipes(in: sectionRecipes, at: offsets)
                                    }
                                }
                            }
                        }

                        // Always offer Google search when user has typed something, even if we have local matches.
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
                }
            }
            .navigationTitle("Mina recept")
            .searchable(text: $searchText, placement: .navigationBarDrawer(displayMode: .always), prompt: "Sök recept")
            .navigationDestination(for: RecipeDTO.self) { recipe in
                RecipeDetailView(recipe: recipe)
            }
            .toolbar {
                ToolbarItemGroup(placement: .topBarTrailing) {
                    Button {
                        showCreateSheet = true
                    } label: {
                        Image(systemName: "plus")
                    }

                    Button("Logga ut") { session.logout() }
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
            .background(
                TabReselectDetector { _ in
                    performHomeReset()
                }
                .frame(width: 0, height: 0)
            )
            .onChange(of: resetToken) { _ in
                performHomeReset()
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

    private var sectionCategoryNames: [String] {
        if let selectedCategory {
            return [selectedCategory]
        }
        return categoryNames
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
                                dismissSearch()
                            }
                            .buttonStyle(.borderedProminent)
                        } else {
                            Button("Alla") {
                                selectedCategory = nil
                                dismissSearch()
                            }
                            .buttonStyle(.bordered)
                        }
                    }

                    ForEach(categoryNames, id: \.self) { category in
                        Group {
                            if selectedCategory == category {
                                Button(category) {
                                    selectedCategory = category
                                    dismissSearch()
                                }
                                .buttonStyle(.borderedProminent)
                            } else {
                                Button(category) {
                                    selectedCategory = category
                                    dismissSearch()
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
        } catch {
            errorMessage = APIError.userFacingMessage(for: error)
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
