/**
 * Minimal Amazon Cognito sign-in for collection points.
 *
 * Calls the public Cognito Identity Provider endpoint directly (USER_PASSWORD_AUTH), so the app needs no
 * extra SDK. The returned ID token is sent to the API, where the API Gateway JWT authorizer verifies it.
 */

const CLIENT_ID = (import.meta.env.VITE_COGNITO_CLIENT_ID ?? "").trim();
const REGION = (import.meta.env.VITE_COGNITO_REGION ?? "ap-south-1").trim();

/** When no client ID is configured (local dev) the app falls back to the shared-key sign-in. */
export const COGNITO_ENABLED = CLIENT_ID !== "";

export class CognitoError extends Error {
  readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.name = "CognitoError";
    this.code = code;
  }
}

interface InitiateAuthResponse {
  AuthenticationResult?: { IdToken?: string };
  ChallengeName?: string;
  __type?: string;
  message?: string;
}

export async function signInWithCognito(username: string, password: string): Promise<string> {
  let response: Response;
  try {
    response = await fetch(`https://cognito-idp.${REGION}.amazonaws.com/`, {
      method: "POST",
      headers: {
        "content-type": "application/x-amz-json-1.1",
        "x-amz-target": "AWSCognitoIdentityProviderService.InitiateAuth",
      },
      body: JSON.stringify({
        AuthFlow: "USER_PASSWORD_AUTH",
        ClientId: CLIENT_ID,
        AuthParameters: { USERNAME: username, PASSWORD: password },
      }),
    });
  } catch {
    throw new CognitoError("NETWORK", "Can't reach the sign-in service. Check your connection and try again.");
  }

  const payload = (await response.json().catch(() => ({}))) as InitiateAuthResponse;
  const token = payload.AuthenticationResult?.IdToken;
  if (response.ok && token) return token;

  const code = payload.__type?.split("#").pop() ?? "UNKNOWN";
  if (code === "NotAuthorizedException" || code === "UserNotFoundException") {
    throw new CognitoError(code, "Those details don't match. Check the ID and password you were given.");
  }
  if (payload.ChallengeName) {
    throw new CognitoError("CHALLENGE", "This account needs a password reset. Ask the administrator.");
  }
  throw new CognitoError(code, "Sign in failed. Please try again.");
}
