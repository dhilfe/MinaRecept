import SwiftUI

struct ShoppingListDetailView: View {
    @EnvironmentObject private var session: SessionController

    let list: ShoppingListDTO

    @State private var items: [ShoppingListItemDTO] = []
    @State private var isLoading: Bool = false
    @State private var errorMessage: String? = nil

    var body: some View {
        List {
            if items.isEmpty && !isLoading {
                Text("Inga rader ännu.")
                    .foregroundStyle(.secondary)
            }

            ForEach(items) { item in
                HStack(spacing: 12) {
                    Image(systemName: item.checked ? "checkmark.circle.fill" : "circle")
                        .foregroundStyle(item.checked ? .green : .secondary)

                    VStack(alignment: .leading, spacing: 2) {
                        Text(itemTitle(item))
                            .strikethrough(item.checked)

                        if let detail = itemDetail(item) {
                            Text(detail)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }

                    Spacer()
                }
                .padding(.vertical, 4)
            }
        }
        .navigationTitle(list.name)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            if isLoading {
                ToolbarItem(placement: .topBarTrailing) {
                    ProgressView()
                }
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
            await load()
        }
        .refreshable {
            await load()
        }
    }

    private func load() async {
        guard let token = session.token else { return }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            items = try await APIClient.shared.fetchShoppingListItems(shoppingListId: list.id, token: token)
        } catch {
            errorMessage = APIError.userFacingMessage(for: error)
        }
    }

    private func itemTitle(_ item: ShoppingListItemDTO) -> String {
        item.name
    }

    private func itemDetail(_ item: ShoppingListItemDTO) -> String? {
        let parts = [item.amount, item.unit]
            .compactMap { $0?.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
        return parts.isEmpty ? nil : parts.joined(separator: " ")
    }
}
