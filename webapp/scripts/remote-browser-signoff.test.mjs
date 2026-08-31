import assert from "node:assert/strict";
import test from "node:test";

import {
  RETIRED_SHELL_REDIRECTS,
  redirectsMatchRetiredShellContract,
} from "./remote-browser-signoff.mjs";


test("retired shell redirects require React targets for normal and legacy-query URLs", () => {
  const redirects = RETIRED_SHELL_REDIRECTS.map((entry) => ({
    path: entry.path,
    status: 308,
    location: entry.expectedLocation,
  }));

  assert.equal(redirectsMatchRetiredShellContract(redirects), true);
  assert.deepEqual(
    RETIRED_SHELL_REDIRECTS.filter((entry) => entry.path.includes("legacy=1")).map((entry) => entry.expectedLocation),
    ["/app/login", "/app/admin", "/app/support", "/app/help", "/app/ticket", "/app/ticket/T-100"],
  );
});


test("retired shell redirects reject a legacy shell response", () => {
  const redirects = RETIRED_SHELL_REDIRECTS.map((entry) => ({
    path: entry.path,
    status: 308,
    location: entry.expectedLocation,
  }));
  redirects[4].location = "/admin?legacy=1&_shell=20260419a";

  assert.equal(redirectsMatchRetiredShellContract(redirects), false);
});
