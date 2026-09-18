/// User-facing, provider-neutral error categories for the food-analysis flow.
/// Never carries raw backend/provider text, model ids, or stack traces -
/// UI copy is derived separately from these cases only.
public enum FoodAnalysisError: Error, Equatable, Sendable {
    case noConnection
    case timeout
    case backendUnavailable
    case rateLimited
    case unauthorized
    case invalidResponse
    case analysisFailed
    /// The picked photo could not be decoded/re-encoded on-device.
    case imageProcessingFailed
    /// No image was selected (or it was empty) when an image call was made.
    case imageMissingOrEmpty
    /// The backend rejected the image's MIME type.
    case unsupportedImageType
    /// The backend rejected the image for exceeding the size limit.
    case imageTooLarge
    /// An `AccessTokenProviding` implementation failed to produce a token
    /// before the request could even be sent (e.g. interactive Entra ID
    /// sign-in is required, or a refresh silently failed). Distinct from
    /// `.unauthorized`, which is the backend itself rejecting the request
    /// after it was sent.
    case authenticationRequired
    case operationInterrupted
    case operationAccountChanged
    case operationConsumed
    case operationConflict
    case operationRequired
    case pilotUnavailable
    case pilotForbidden
    case pilotLimit
    case pilotInput

    public var canRetryOperation: Bool {
        isRetryEligible || self == .authenticationRequired || self == .unauthorized
            || self == .operationInterrupted || self == .pilotUnavailable || self == .pilotLimit
    }

    public var requiresNewOperationConfirmation: Bool {
        switch self {
        case .noConnection, .timeout, .backendUnavailable, .rateLimited, .invalidResponse,
             .analysisFailed, .operationInterrupted, .operationConsumed, .operationConflict,
             .operationRequired, .pilotUnavailable, .operationAccountChanged:
            return true
        default:
            return false
        }
    }

    /// Whether an explicit "Erneut versuchen" retry action makes sense for
    /// this failure. Only failures where an identical retry could
    /// plausibly succeed without any change to the input (connectivity,
    /// a temporarily unavailable backend, rate limiting, or a timeout) are
    /// eligible; input/configuration problems are not, since retrying the
    /// exact same request would just fail the same way again.
    public var isRetryEligible: Bool {
        switch self {
        case .noConnection, .timeout, .backendUnavailable, .rateLimited, .analysisFailed:
            return true
        case .unauthorized, .invalidResponse, .imageProcessingFailed, .imageMissingOrEmpty,
            .unsupportedImageType, .imageTooLarge, .authenticationRequired, .operationInterrupted,
            .operationConsumed, .operationConflict, .operationRequired, .pilotUnavailable,
            .pilotForbidden, .pilotLimit, .pilotInput:
            return false
        case .operationAccountChanged:
            return false
        }
    }

    public var userMessage: String {
        switch self {
        case .noConnection:
            return "Die Verbindung ist unterbrochen. Die Analyse könnte serverseitig trotzdem ausgeführt worden sein."
        case .timeout:
            return "Keine rechtzeitige Antwort. Ob die Analyse ausgeführt wurde, ist unklar."
        case .backendUnavailable:
            return "Der Analysedienst ist nicht erreichbar. Der Ausgang dieser Anfrage ist unklar."
        case .rateLimited:
            return "Zu viele Anfragen. Bitte warte einen Moment und versuche es erneut."
        case .unauthorized:
            return "Die Analyse ist momentan nicht verfügbar."
        case .invalidResponse:
            return "Die Antwort konnte nicht verarbeitet werden. Beim KI-Anbieter könnte bereits Verbrauch entstanden sein."
        case .analysisFailed:
            return "Es liegt kein nutzbares Ergebnis vor. Ob beim KI-Anbieter Verbrauch entstanden ist, ist unklar."
        case .imageProcessingFailed:
            return "Das Foto konnte nicht verarbeitet werden. Bitte wähle ein anderes Foto."
        case .imageMissingOrEmpty:
            return "Es wurde kein gültiges Foto übermittelt. Bitte wähle ein Foto aus."
        case .unsupportedImageType:
            return "Dieses Bildformat wird nicht unterstützt. Bitte verwende ein JPEG- oder PNG-Foto."
        case .imageTooLarge:
            return "Das Foto ist zu groß. Bitte wähle ein kleineres Foto."
        case .authenticationRequired:
            return "Anmeldung erforderlich. Bitte versuche es erneut."
        case .operationInterrupted:
            return "Die Anfrage wurde hier abgebrochen. Serverseitig kann sie weiterlaufen; ihr Ausgang ist unklar."
        case .operationAccountChanged:
            return "Das angemeldete Konto hat gewechselt. Der bestehende Vorgang wird mit diesem Konto nicht erneut gesendet. Eine neue Berechnung muss ausdrücklich bestätigt werden."
        case .operationConsumed:
            return "Diese Anfrage wurde bereits angenommen. Sie kann noch laufen, abgeschlossen oder ihr Ausgang unbekannt sein. Das Ergebnis kann nicht erneut abgerufen werden."
        case .operationConflict:
            return "Die Vorgangs-ID gehört zu einem anderen Anfrageinhalt. Diese Anfrage wird nicht erneut gesendet."
        case .operationRequired:
            return "Die Vorgangs-ID ist ungültig oder abgelaufen. Sie wird nicht automatisch ersetzt. Bitte prüfe auch die Gerätezeit."
        case .pilotUnavailable:
            return "Die Anfrage konnte nicht sicher bestätigt werden. Beim KI-Anbieter könnte bereits Verbrauch entstanden sein."
        case .pilotForbidden:
            return "Dieses Konto ist nicht für die Analyse freigegeben."
        case .pilotLimit:
            return "Das freigegebene Nutzungslimit ist erreicht. Es wird keine neue Anfrage gestartet."
        case .pilotInput:
            return "Die Eingabe überschreitet die freigegebenen Analysegrenzen."
        }
    }
}
