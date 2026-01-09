import SwiftUI

struct RecipePickerView: View {
    @EnvironmentObject private var session: SessionController
    @Environment(\.dismiss) private var dismiss
    
    let onSelect: (RecipeDTO) -> Void
    
    @State private var recipes: [RecipeDTO] = []
    @State private var isLoading = false
    @State private var errorMessage: String?
    
    var body: some View {
        NavigationStack {
            List(recipes) { recipe in
                Button {
                    onSelect(recipe)
                    dismiss()
                } label: {
                    HStack {
                        if let url = recipe.preferredImageURL {
                            AsyncImage(url: url) { image in
                                image.resizable().scaledToFill()
                            } placeholder: {
                                Color.gray.opacity(0.3)
                            }
                            .frame(width: 50, height: 50)
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                        }
                        Text(recipe.title)
                            .foregroundStyle(.primary)
                    }
                }
            }
            .navigationTitle("Välj recept")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Avbryt") { dismiss() }
                }
            }
            .task {
                await loadRecipes()
            }
            .overlay {
                if isLoading { ProgressView() }
            }
        }
    }
    
    private func loadRecipes() async {
        guard let token = session.token else { return }
        isLoading = true
        defer { isLoading = false }
        do {
            recipes = try await APIClient.shared.fetchRecipes(token: token)
        } catch {
            errorMessage = APIError.userFacingMessage(for: error)
        }
    }
}

struct RecipeMultiPickerView: View {
    @EnvironmentObject private var session: SessionController
    @Environment(\.dismiss) private var dismiss

    let onSelect: ([RecipeDTO]) -> Void

    @State private var recipes: [RecipeDTO] = []
    @State private var selectedIds: Set<Int> = []
    @State private var isLoading = false
    @State private var errorMessage: String?

    private var selectedRecipes: [RecipeDTO] {
        recipes.filter { selectedIds.contains($0.id) }
    }

    var body: some View {
        NavigationStack {
            List {
                if !recipes.isEmpty {
                    Section {
                        Button {
                            selectedIds = Set(recipes.map { $0.id })
                        } label: {
                            Text("Markera alla")
                        }

                        Button {
                            selectedIds = []
                        } label: {
                            Text("Avmarkera alla")
                        }
                        .disabled(selectedIds.isEmpty)
                    }
                }

                Section {
                    ForEach(recipes) { recipe in
                        Button {
                            if selectedIds.contains(recipe.id) {
                                selectedIds.remove(recipe.id)
                            } else {
                                selectedIds.insert(recipe.id)
                            }
                        } label: {
                            HStack(spacing: 12) {
                                if let url = recipe.preferredImageURL {
                                    AsyncImage(url: url) { image in
                                        image.resizable().scaledToFill()
                                    } placeholder: {
                                        Color.gray.opacity(0.3)
                                    }
                                    .frame(width: 44, height: 44)
                                    .clipShape(RoundedRectangle(cornerRadius: 10))
                                }

                                Text(recipe.title)
                                    .foregroundStyle(.primary)
                                    .lineLimit(2)

                                Spacer(minLength: 0)

                                if selectedIds.contains(recipe.id) {
                                    Image(systemName: "checkmark.circle.fill")
                                        .foregroundStyle(.accent)
                                } else {
                                    Image(systemName: "circle")
                                        .foregroundStyle(.secondary)
                                }
                            }
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
            .navigationTitle("Välj recept")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Avbryt") { dismiss() }
                }

                ToolbarItem(placement: .confirmationAction) {
                    Button {
                        onSelect(selectedRecipes)
                        dismiss()
                    } label: {
                        Text("Lägg till (\(selectedIds.count))")
                    }
                    .disabled(selectedIds.isEmpty)
                }

                if isLoading {
                    ToolbarItem(placement: .topBarLeading) {
                        ProgressView()
                    }
                }
            }
            .task {
                await loadRecipes()
            }
            .overlay {
                if isLoading { ProgressView() }
            }
            .safeAreaInset(edge: .bottom) {
                if let errorMessage {
                    Text(errorMessage)
                        .frame(maxWidth: .infinity)
                        .padding(12)
                        .background(.thinMaterial)
                }
            }
        }
    }

    private func loadRecipes() async {
        guard let token = session.token else { return }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            recipes = try await APIClient.shared.fetchRecipes(token: token)
        } catch {
            errorMessage = APIError.userFacingMessage(for: error)
        }
    }
}
