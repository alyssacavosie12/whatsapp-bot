(() => {
  "use strict";

  const KEY_STORAGE_NAME = "adminFernetKey";
  const KEY_IDLE_TIMEOUT_MS = 30 * 60 * 1000;
  const decoder = new TextDecoder();
  let keyAutoClearTimer = 0;

  function base64UrlToBytes(value) {
    let normalized = value.trim().replace(/-/g, "+").replace(/_/g, "/");
    while (normalized.length % 4) {
      normalized += "=";
    }

    const binary = atob(normalized);
    const bytes = new Uint8Array(binary.length);

    for (let index = 0; index < binary.length; index += 1) {
      bytes[index] = binary.charCodeAt(index);
    }

    return bytes;
  }

  function constantTimeEqual(left, right) {
    if (left.length !== right.length) {
      return false;
    }

    let diff = 0;
    for (let index = 0; index < left.length; index += 1) {
      diff |= left[index] ^ right[index];
    }

    return diff === 0;
  }

  async function importFernetKeys(keyText) {
    const keyBytes = base64UrlToBytes(keyText);

    if (keyBytes.length !== 32) {
      throw new Error("Fernet key must decode to 32 bytes");
    }

    const signingKey = keyBytes.slice(0, 16);
    const encryptionKey = keyBytes.slice(16, 32);

    return {
      signingKey: await crypto.subtle.importKey(
        "raw",
        signingKey,
        { name: "HMAC", hash: "SHA-256" },
        false,
        ["sign"],
      ),
      encryptionKey: await crypto.subtle.importKey(
        "raw",
        encryptionKey,
        { name: "AES-CBC" },
        false,
        ["decrypt"],
      ),
    };
  }

  async function decryptFernetToken(tokenText, keyText) {
    const keys = await importFernetKeys(keyText);
    const token = base64UrlToBytes(tokenText);

    if (token.length < 1 + 8 + 16 + 1 + 32) {
      throw new Error("Fernet token is too short");
    }

    if (token[0] !== 0x80) {
      throw new Error("Unsupported Fernet token version");
    }

    const signedPayload = token.slice(0, token.length - 32);
    const expectedMac = token.slice(token.length - 32);
    const actualMac = new Uint8Array(
      await crypto.subtle.sign("HMAC", keys.signingKey, signedPayload),
    );

    if (!constantTimeEqual(expectedMac, actualMac)) {
      throw new Error("Invalid Fernet signature");
    }

    const iv = token.slice(9, 25);
    const ciphertext = token.slice(25, token.length - 32);
    const plaintext = new Uint8Array(
      await crypto.subtle.decrypt(
        { name: "AES-CBC", iv },
        keys.encryptionKey,
        ciphertext,
      ),
    );

    return decoder.decode(plaintext);
  }

  function getKeyInput() {
    return document.querySelector("[data-fernet-key]");
  }

  function setStatus(text, isError = false) {
    const status = document.querySelector("[data-decrypt-status]");
    if (!status) {
      return;
    }

    status.textContent = text;
    status.hidden = false;
    status.dataset.error = isError ? "true" : "false";
  }

  function clearKeyAutoClearTimer() {
    if (!keyAutoClearTimer) {
      return;
    }

    clearTimeout(keyAutoClearTimer);
    keyAutoClearTimer = 0;
  }

  function hasKeyMaterial() {
    const input = getKeyInput();
    const typedKey = input ? input.value.trim() : "";

    return Boolean(typedKey || sessionStorage.getItem(KEY_STORAGE_NAME));
  }

  function clearStoredKey(message, isError = false) {
    clearKeyAutoClearTimer();
    sessionStorage.removeItem(KEY_STORAGE_NAME);

    const input = getKeyInput();
    if (input) {
      input.value = "";
    }

    setStatus(message, isError);
  }

  function scheduleKeyAutoClear() {
    clearKeyAutoClearTimer();

    if (!hasKeyMaterial()) {
      return;
    }

    keyAutoClearTimer = setTimeout(() => {
      clearStoredKey("Key auto-cleared after 30 minutes of inactivity.", true);
    }, KEY_IDLE_TIMEOUT_MS);
  }

  function recordKeyActivity() {
    if (hasKeyMaterial()) {
      scheduleKeyAutoClear();
    }
  }

  function getCurrentKey() {
    const input = getKeyInput();
    if (!input) {
      return "";
    }

    const typedKey = input.value.trim();
    if (typedKey) {
      sessionStorage.setItem(KEY_STORAGE_NAME, typedKey);
      scheduleKeyAutoClear();
      return typedKey;
    }

    const savedKey = sessionStorage.getItem(KEY_STORAGE_NAME) || "";

    if (savedKey) {
      scheduleKeyAutoClear();
    }

    return savedKey;
  }

  async function decryptElement(element) {
    const key = getCurrentKey();
    if (!key) {
      setStatus("Enter the Fernet key first. The key stays in this browser tab.", true);
      return;
    }

    const token = element.dataset.fernetToken || "";
    const output = element.querySelector("[data-decrypted-output]");
    const decryptButton = element.querySelector("[data-decrypt-one]");
    const hideButton = element.querySelector("[data-hide-decrypted]");
    const result = element.querySelector("[data-decrypt-result]");

    if (!token || !output) {
      return;
    }

    try {
      const plaintext = await decryptFernetToken(token, key);
      output.textContent = plaintext;
      output.hidden = false;
      if (decryptButton) {
        decryptButton.hidden = true;
      }
      if (hideButton) {
        hideButton.hidden = false;
      }
      if (result) {
        result.hidden = false;
      }
      element.dataset.decrypted = "true";
      setStatus("Message decrypted locally in your browser.");
    } catch (error) {
      output.textContent = "Decrypt failed. Check the Fernet key.";
      output.hidden = false;
      setStatus("Decrypt failed. Check the Fernet key.", true);
    }
  }

  async function decryptAll() {
    const encryptedElements = Array.from(document.querySelectorAll("[data-fernet-token]"));
    if (!encryptedElements.length) {
      setStatus("No encrypted messages on this page.");
      return;
    }

    for (const element of encryptedElements) {
      await decryptElement(element);
    }
  }

  function hideDecryptedElement(element) {
    const output = element.querySelector("[data-decrypted-output]");
    const decryptButton = element.querySelector("[data-decrypt-one]");
    const hideButton = element.querySelector("[data-hide-decrypted]");
    const result = element.querySelector("[data-decrypt-result]");

    if (output) {
      output.hidden = true;
    }
    if (decryptButton) {
      decryptButton.hidden = false;
    }
    if (hideButton) {
      hideButton.hidden = true;
    }
    if (result) {
      result.hidden = true;
    }

    delete element.dataset.decrypted;
  }

  async function copyValue(button) {
    const value = button.dataset.copyValue || "";
    if (!value) {
      return;
    }

    const originalText = button.textContent;

    try {
      await navigator.clipboard.writeText(value);
      button.textContent = "Copied";
      setTimeout(() => {
        button.textContent = originalText;
      }, 1500);
    } catch (error) {
      button.textContent = "Copy failed";
      setTimeout(() => {
        button.textContent = originalText;
      }, 1500);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    const input = getKeyInput();
    const savedKey = sessionStorage.getItem(KEY_STORAGE_NAME);

    if (input && savedKey) {
      input.value = savedKey;
    }

    scheduleKeyAutoClear();

    if (input) {
      input.addEventListener("input", recordKeyActivity);
    }

    for (const eventName of ["keydown", "touchstart"]) {
      document.addEventListener(eventName, recordKeyActivity);
    }

    document.addEventListener("click", (event) => {
      recordKeyActivity();

      const target = event.target;
      if (!(target instanceof HTMLElement)) {
        return;
      }

      const copyButton = target.closest("[data-copy-value]");
      if (copyButton instanceof HTMLElement) {
        void copyValue(copyButton);
        return;
      }

      const hideDecrypted = target.closest("[data-hide-decrypted]");
      if (hideDecrypted) {
        const encryptedElement = hideDecrypted.closest("[data-fernet-token]");
        if (encryptedElement instanceof HTMLElement) {
          hideDecryptedElement(encryptedElement);
        }
        return;
      }

      const decryptOne = target.closest("[data-decrypt-one]");
      if (decryptOne) {
        const encryptedElement = decryptOne.closest("[data-fernet-token]");
        if (encryptedElement instanceof HTMLElement) {
          void decryptElement(encryptedElement);
        }
        return;
      }

      if (target.closest("[data-decrypt-all]")) {
        void decryptAll();
      }

      if (target.closest("[data-forget-fernet-key]")) {
        clearStoredKey("Fernet key removed from this browser tab.");
      }
    });
  });
})();
