import SwiftUI
import AuthenticationServices

struct LoginView: View {
    @EnvironmentObject private var session: SessionController
    @Environment(\.colorScheme) var colorScheme

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
                Section {
                    SignInWithAppleButton(.signIn) { request in
                        request.requestedScopes = [.fullName, .email]
                    } onCompletion: { result in
                        handleAppleLogin(result)
                    }
                    .signInWithAppleButtonStyle(colorScheme == .dark ? .white : .black)
                    .frame(height: 50)
                    .listRowInsets(EdgeInsets()) // Edge-to-edge button
                    .padding(.vertical, 8)
                } header: {
                    Text("Snabbinloggning")
                } footer: {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("Logga in eller skapa konto automatiskt med ditt Apple ID.")
#if DEBUG
                        Text("API: \(AppConfig.apiBaseURL.absoluteString)")
                            .font(.caption)
                            .foregroundStyle(.secondary)
#endif
                    }
                }

                Section("Eller logga in med lösenord") {
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
            .navigationTitle("MinaRecept")
            .toolbar {
                ToolbarItemGroup(placement: .keyboard) {
                    Spacer()
                    Button("Klar") { focusField = nil }
                }
            }
            .onAppear {
                // Optional: focus username if preferred, but maybe better to let user choose apple login first
                // focusField = .username
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
            if let apiError = error as? APIError, case .httpStatus(400, _) = apiError {
                errorMessage = "Fel användarnamn eller lösenord."
            } else {
                errorMessage = APIError.userFacingMessage(for: error)
            }
        }
    }

    private func handleAppleLogin(_ result: Result<ASAuthorization, Error>) {
        errorMessage = nil
        isLoading = true
        
        switch result {
        case .success(let authorization):
            guard let appleIDCredential = authorization.credential as? ASAuthorizationAppleIDCredential else {
                errorMessage = "Kunde inte läsa Apple ID-uppgifter."
                isLoading = false
                return
            }

            guard let identityTokenData = appleIDCredential.identityToken,
                  let identityToken = String(data: identityTokenData, encoding: .utf8) else {
                errorMessage = "Kunde inte hämta identity token."
                isLoading = false
                return
            }

            // Name is only available on first login
            let firstName = appleIDCredential.fullName?.givenName
            let lastName = appleIDCredential.fullName?.familyName

            Task {
                do {
                    let token = try await APIClient.shared.loginWithApple(
                        idToken: identityToken,
                        firstName: firstName,
                        lastName: lastName
                    )
                    await MainActor.run {
                        session.setToken(token)
                        isLoading = false
                    }
                } catch {
                    await MainActor.run {
                        errorMessage = APIError.userFacingMessage(for: error)
                        isLoading = false
                    }
                }
            }

        case .failure(let error):
            // Check for user cancellation
            if let asError = error as? ASAuthorizationError, asError.code == .canceled {
                // User cancelled, do nothing
                isLoading = false
                return
            }
            errorMessage = "Apple Login misslyckades: \(error.localizedDescription)"
            isLoading = false
        }
    }
}
