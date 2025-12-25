import SwiftUI

struct ShoppingListsView: View {
    @EnvironmentObject private var session: SessionController

    @State private var lists: [ShoppingListDTO] = []
    @State private var isLoading: Bool = false
    @State private var errorMessage: String? = nil

    var body: some View {
        NavigationStack {
            List(lists) { list in
                NavigationLink(value: list) {
                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(list.name)
                                .font(.headline)

                            if list.isRecurring {
                                Text("Återkommande")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        }
                        Spacer()
                    }
                }
            }
            .navigationTitle("Inköpslistor")
            .navigationDestination(for: ShoppingListDTO.self) { list in
                ShoppingListDetailView(list: list)
            }
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Logga ut") { session.logout() }
                }

                if isLoading {
                    ToolbarItem(placement: .topBarLeading) {
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
    }

    private func load() async {
        guard let token = session.token else { return }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            lists = try await APIClient.shared.fetchShoppingLists(token: token)
        } catch {
            errorMessage = APIError.userFacingMessage(for: error)
        }
    }
}
