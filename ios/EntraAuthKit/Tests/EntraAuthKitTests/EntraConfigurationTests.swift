import XCTest

@testable import EntraAuthKit

final class EntraConfigurationTests: XCTestCase {
    func test_load_returnsConfigurationWhenAllFourKeysPresent() {
        let bundle = FakeInfoDictionaryBundle(values: [
            "EntraTenantID": "11111111-1111-1111-1111-111111111111",
            "EntraClientID": "22222222-2222-2222-2222-222222222222",
            "EntraAPIScope": "api://backend-app-id/FoodAnalysis.Access",
            "EntraRedirectURI": "msauth.com.example.app://auth",
        ])

        let configuration = EntraConfiguration.load(bundle: bundle)

        XCTAssertEqual(configuration?.tenantId, "11111111-1111-1111-1111-111111111111")
        XCTAssertEqual(configuration?.apiScope, "api://backend-app-id/FoodAnalysis.Access")
        XCTAssertEqual(configuration?.authority, "https://login.microsoftonline.com/11111111-1111-1111-1111-111111111111")
    }

    func test_load_returnsNilWhenAnySingleKeyIsMissing() {
        let bundle = FakeInfoDictionaryBundle(values: [
            "EntraTenantID": "11111111-1111-1111-1111-111111111111",
            "EntraClientID": "22222222-2222-2222-2222-222222222222",
            "EntraAPIScope": "api://backend-app-id/FoodAnalysis.Access",
            // EntraRedirectURI intentionally omitted.
        ])

        XCTAssertNil(EntraConfiguration.load(bundle: bundle))
    }

    func test_load_returnsNilWhenAKeyIsBlank() {
        let bundle = FakeInfoDictionaryBundle(values: [
            "EntraTenantID": "   ",
            "EntraClientID": "22222222-2222-2222-2222-222222222222",
            "EntraAPIScope": "api://backend-app-id/FoodAnalysis.Access",
            "EntraRedirectURI": "msauth.com.example.app://auth",
        ])

        XCTAssertNil(EntraConfiguration.load(bundle: bundle))
    }

    func test_load_returnsNilWhenNoKeysArePresentAtAll() {
        XCTAssertNil(EntraConfiguration.load(bundle: FakeInfoDictionaryBundle(values: [:])))
    }
}

/// A real `Bundle` cannot be given an arbitrary Info.plist dictionary in a
/// SwiftPM test target, so `EntraConfiguration.load(bundle:)` is exercised
/// through this minimal subclass instead.
private final class FakeInfoDictionaryBundle: Bundle, @unchecked Sendable {
    private let values: [String: String]

    init(values: [String: String]) {
        self.values = values
        super.init()
    }

    override func object(forInfoDictionaryKey key: String) -> Any? {
        values[key]
    }
}
