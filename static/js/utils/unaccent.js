/**
 * Accent-insensitive string utilities
 *
 * Provides functions to remove accents from strings for liberal searching.
 * For example, searching for "si" will match "sí", "Sí Bheag", etc.
 *
 * Uses Unicode normalization (NFD) for comprehensive accent removal.
 */

(function(window) {
    'use strict';

    /**
     * Remove accents from a string using Unicode normalization
     * @param {string} str - The input string
     * @returns {string} - String with accents removed
     */
    function removeAccents(str) {
        if (!str) return '';

        // Decompose combined characters and remove combining diacritical marks
        // NFD = Canonical Decomposition, \u0300-\u036f = combining diacritical marks range
        return str.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
    }

    /**
     * Normalize a string for accent-insensitive comparison
     * Removes accents and converts to lowercase
     * @param {string} str - The input string
     * @returns {string} - Normalized string
     */
    function normalize(str) {
        if (!str) return '';
        return removeAccents(str).toLowerCase();
    }

    /**
     * Check if a string includes another string (accent-insensitive)
     * @param {string} haystack - The string to search in
     * @param {string} needle - The string to search for
     * @returns {boolean} - True if needle is found in haystack
     */
    function includesIgnoringAccents(haystack, needle) {
        if (!haystack || !needle) return false;
        return normalize(haystack).includes(normalize(needle));
    }

    /**
     * Check if two strings are equal (accent-insensitive, case-insensitive)
     * @param {string} str1 - First string
     * @param {string} str2 - Second string
     * @returns {boolean} - True if strings are equal
     */
    function equalsIgnoringAccents(str1, str2) {
        if (!str1 && !str2) return true;
        if (!str1 || !str2) return false;
        return normalize(str1) === normalize(str2);
    }

    // Export to global scope
    window.AccentUtils = {
        removeAccents: removeAccents,
        normalize: normalize,
        includes: includesIgnoringAccents,
        equals: equalsIgnoringAccents
    };

})(window);
