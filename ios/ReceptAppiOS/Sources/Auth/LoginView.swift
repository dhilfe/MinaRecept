import SwiftUI

struct LoginView: View {
    @EnvironmentObject private var session: SessionController

    @State private var username: String = ""
    @State private var password: String = ""
    @State private var isLoading: Bool = false
    @State private var errorMessage: String? = nil

    private enum FocusField {
        case username
        case password
    }

    @FocusState private var focusField: FocusField?

    var body: some View {
        NavigationStack {
            Form {
                Section("Inloggning") {
                    TextField("Användarnamn", text: $username)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled(true)
                        .textContentType(.username)
                        .keyboardType(.asciiCapable)
                        .submitLabel(.next)
                        .focused($focusField, equals: .username)
                        .onSubmit {
                            focusField = .password
                        }

                    SecureField("Lösenord", text: $password)
                        .textContentType(.password)
                        .submitLabel(.go)
                        .focused($focusField, equals: .password)
                        .onSubmit {
                            guard !isLoading, !username.isEmpty, !password.isEmpty else { return }
                            Task { await login() }
                        }
                }

                if let errorMessage {
                    Section {
                        Text(errorMessage)
                            .foregroundStyle(.red)
                    }
                }

                Section {
                    Button {
                        Task { await login() }
                    } label: {
                        if isLoading {
                            ProgressView()
                        } else {
                            Text("Logga in")
                        }
                    }
                    .disabled(isLoading || username.isEmpty || password.isEmpty)
                }
            }
            .navigationTitle("ReceptApp")
            .toolbar {
                ToolbarItemGroup(placement: .keyboard) {
                    Spacer()
                    Button("Klar") { focusField = nil }
                }
            }
            .onAppear {
                focusField = .username
            }
        }
    }

    private func login() async {
        errorMessage = nil
        isLoading = true
        defer { isLoading = false }

        do {
            let token = try await APIClient.shared.login(username: username, password: password)
            session.setToken(token)
        } catch {
            errorMessage = APIError.userFacingMessage(for: error)
        }
    }
}
