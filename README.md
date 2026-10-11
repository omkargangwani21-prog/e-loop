# E-Loop

Schedule an e-waste pickup. A photo suggests what the item is, the nearest suitable collection point is matched
automatically, and every collection is weighed and recorded in a tamper-evident ledger that producers and auditors
can verify.

Built for **Environmental Hacks (WeMakeDevs x AWS), Waste and Energy track**.

## Why this is more than a pickup form

India's e-waste rules put recycling targets on producers (Extended Producer Responsibility) and require proof of
collection. Households have no easy way to dispose of devices, and informal collectors cannot prove what they handled.
E-Loop sits in the middle: it creates a **verifiable collection record** for every pickup. That record, aggregated, is
what a producer or compliance body pays for.

## Architecture

```
Browser (React, Amplify Hosting)
   |  presigned POST            |  HTTPS JSON
   v                            v
 S3 uploads/  <----------  API Gateway (HTTP API)  ->  Lambda (Python 3.12)
   |  DetectLabels                                        |-- DynamoDB (single table + 1 GSI)
   +--> Rekognition  (Bedrock optional, manual fallback)  |-- SNS (collector alerts, no PII)
                                                          +-- SSM (collector key secret)
```

| Concern | Choice | Reason |
| --- | --- | --- |
| Image upload | S3 presigned POST with size and type conditions | The photo never passes through Lambda; limits are enforced by S3, not by trust. |
| Classification | `ClassifierChain`: Rekognition, then Bedrock, then manual | Any AI service can be throttled or gated (Bedrock was for us). The product still works; the user just picks the item. |
| Persistence | DynamoDB, one table, `TransactWriteItems` per state change | Conditional version check means two collectors cannot both accept one pickup; counters update atomically. |
| Ledger | SHA-256 hash chain, events hold only `str`/`int`/`bool` | Cheap integrity proof. Floats are banned so hashes survive DynamoDB's Decimal round trip. |
| Privacy | Contact details revealed only after a collector accepts; items expire via DynamoDB TTL; SNS messages carry no PII | Data minimisation by default. |
| Matching | Haversine nearest accepting collector within `MAX_MATCH_KM` | Simple and explainable; swap for Amazon Location Service later. |

## Run it locally (no AWS account needed)

```bash
make install
make api        # terminal 1: API on :8787, prints sign-in keys for the demo collection points
make web        # terminal 2: web app on :5173
make test       # backend tests
```

Local mode swaps S3, DynamoDB, SNS and SSM for in-process equivalents behind the same interfaces. Classification is
manual locally; set `CLASSIFIER_CHAIN` and AWS credentials to try Rekognition.

Demo walkthrough: schedule a pickup, copy the tracking code, sign in at **Collector sign in** with `demo-dwarka` and the
key printed by `make api`, accept the pickup, mark it collected, then reload the tracking page and the Impact page.

## Where AWS plugs in (do these in order)

1. **Account and tooling.** Install the AWS CLI and SAM CLI, run `aws configure`, pick a region (`ap-south-1` is the default).
2. **Collector secret (optional now).** Only the local/shared-key fallback uses SSM. In AWS the collectors sign in with Cognito (step 3b).
3. **Deploy the API.** `make deploy`. Note the `ApiUrl` output.
3b. **Collector accounts.** After deploy, run `.\infra\create_collectors.ps1 -UserPoolId <UserPoolId> -Password <password>`, then set `VITE_COGNITO_CLIENT_ID` to the `UserPoolClientId` output.
4. **Check Rekognition.** Upload a phone photo in the app. If the item is not recognised, add the label Rekognition returned to `labels` in `backend/src/eloop/catalog.py`.
5. **Frontend.** In Amplify Hosting, connect the repo (it reads `amplify.yml`), set `VITE_API_BASE_URL` to `ApiUrl`, and add the **Single Page App** rewrite rule under Rewrites and redirects.
6. **CORS.** Redeploy with `AllowedOrigin` set to the Amplify URL (`sam deploy --parameter-overrides AllowedOrigin=https://...`).
7. **Alerts (optional).** Pass `AlertEmail=you@example.com` and confirm the SNS subscription email.
8. **Bedrock (optional).** When access works, set `ClassifierChain=rekognition,bedrock` and `BedrockModelId=<model or inference profile>`.

## Project layout

```
backend/   Python API: service layer, adapters (store, storage, classifier, notify), tests
frontend/  React + TypeScript (Vite), no UI framework, hand-written design system
infra/     SAM template, deploy config, secret bootstrap script
```

## Honest status

Verified in development: 39 backend tests pass (ledger, matching, classifiers with fake AWS clients, full API
lifecycle, auth scoping), and the local server was exercised end to end over HTTP including the multipart upload path.

Not verified, because the build sandbox blocked the package registries and had no AWS access:

- The DynamoDB store has tests (`tests/test_store_dynamo.py`, run against moto) but they were skipped. Run `make test` once.
- The SAM template parses but has not been through `sam validate` or a real deploy.
- The frontend was not compiled or opened in a browser. Run `make install && make typecheck` first and fix anything TypeScript reports.
- Rekognition label mapping is best effort and needs tuning against real photos.

## Placeholders to replace before this is a product

- Collection points in `backend/src/eloop/data/collectors.json` are **demo data**. Scrap values and weights in `catalog.py` are indicative.
- Collector sign-in uses Amazon Cognito (admin-created users, API Gateway JWT authorizer on `/collector/*`). Local dev keeps the derived-key sign-in. Add MFA and a password-reset flow before real use.
- `classified_by` and `confidence` are reported by the client and are informational. The collector's confirmation and weight are the authoritative record.
