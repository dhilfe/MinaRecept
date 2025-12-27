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
