import SwiftUI

struct ShoppingListsView: View {
    @EnvironmentObject private var session: SessionController

    @State private var lists: [ShoppingListDTO] = []
    @State private var isLoading: Bool = false
    @State private var errorMessage: String? = nil
    @State private var showCreateAlert: Bool = false
    @State private var newListName: String = ""

    var body: some View {
        NavigationStack {
            List {
                ForEach(lists) { list in
                    NavigationLink(value: list) {
                        HStack {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(list.name)
                                    .font(.headline)

                                if let count = list.itemCount {
                                    Text("\(count) varor")
                                        .font(.subheadline)
                                        .foregroundStyle(.secondary)
                                }

                                if let date = list.updatedAt {
                                    Text(date.formatted(date: .abbreviated, time: .shortened))
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }

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
                .onDelete(perform: deleteList)
            }
            .navigationTitle("Inköpslistor")
            .navigationDestination(for: ShoppingListDTO.self) { list in
                ShoppingListDetailView(list: list)
            }
            .alert("Ny stående lista", isPresented: $showCreateAlert) {
                TextField("Namn", text: $newListName)
                Button("Avbryt", role: .cancel) { }
                Button("Skapa") {
                    createList()
                }
            } message: {
                Text("Ange namn för den nya stående inköpslistan.")
            }
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    HStack {
                        Button {
                            newListName = ""
                            showCreateAlert = true
                        } label: {
                            Image(systemName: "plus")
                        }
                        
                        Button("Logga ut") { session.logout() }
                    }
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

    private func createList() {
        guard let token = session.token, !newListName.isEmpty else { return }
        
        Task {
            do {
                _ = try await APIClient.shared.createShoppingList(name: newListName, isRecurring: true, token: token)
                await load()
            } catch {
                errorMessage = APIError.userFacingMessage(for: error)
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

    private func deleteList(at offsets: IndexSet) {
        guard let token = session.token else { return }
        
        for index in offsets {
            let list = lists[index]
            Task {
                do {
                    try await APIClient.shared.deleteShoppingList(id: list.id, token: token)
                    await load()
                } catch {
                    errorMessage = APIError.userFacingMessage(for: error)
                }
            }
        }
    }
}
