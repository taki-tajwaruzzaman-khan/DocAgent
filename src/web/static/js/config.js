// Copyright (c) Meta Platforms, Inc. and affiliates
/**
 * Configuration handling for the docstring generation web application.
 *
 * This file provides functions for loading and saving configuration for the
 * docstring generation process.
 */

/**
 * Toggle LLM-specific fields based on the selected LLM type.
 */
function toggleLLMFields() {
    const llmType = $('#llm-type').val();

    if (llmType === 'bedrock') {
        $('#api-key-field').hide();
        $('#bedrock-fields').show();
    } else {
        $('#api-key-field').show();
        $('#bedrock-fields').hide();
    }
}

/**
 * Load the default configuration from the server.
 */
function loadDefaultConfig() {
    $.ajax({
        url: '/api/default_config',
        type: 'GET',
        success: function(config) {
            applyConfigToForm(config);
            toggleLLMFields();
        },
        error: function(xhr, status, error) {
            console.error('Error loading default configuration:', error);
            showMessage('warning', 'Failed to load default configuration. Using fallback values.');
        }
    });
}

// Add event listener for LLM type changes
$(document).ready(function() {
    $('#llm-type').on('change', toggleLLMFields);
    toggleLLMFields(); // Initialize on page load
});

/**
 * Apply a configuration object to the form inputs.
 *
 * @param {Object} config - The configuration object to apply
 */
function applyConfigToForm(config) {
    // Set LLM configuration
    if (config.llm) {
        $('#llm-type').val(config.llm.type || 'claude');
        $('#llm-api-key').val(config.llm.api_key || '');
        $('#llm-model').val(config.llm.model || 'claude-3-5-haiku-latest');
        $('#llm-temperature').val(config.llm.temperature || 0.1);
        $('#llm-max-tokens').val(config.llm.max_tokens || 4096);

        // Set AWS Bedrock fields if present
        if (config.llm.type === 'bedrock') {
            $('#aws-region').val(config.llm.aws_region || 'us-east-1');
            $('#aws-access-key').val(config.llm.aws_access_key || '');
            $('#aws-secret-key').val(config.llm.aws_secret_key || '');
        }
    }

    // Set flow control configuration
    if (config.flow_control) {
        $('#max-reader-search-attempts').val(config.flow_control.max_reader_search_attempts || 2);
        $('#max-verifier-rejections').val(config.flow_control.max_verifier_rejections || 1);
        $('#status-sleep-time').val(config.flow_control.status_sleep_time || 1);
    }

    // Set docstring options
    if (config.docstring_options) {
        $('#overwrite-docstrings').prop('checked', config.docstring_options.overwrite_docstrings || false);
    }
}

/**
 * Build a configuration object from the form inputs.
 *
 * @returns {Object} The configuration object
 */
function buildConfigFromForm() {
    const llmType = $('#llm-type').val();
    const config = {
        llm: {
            type: llmType,
            model: $('#llm-model').val(),
            temperature: parseFloat($('#llm-temperature').val()),
            max_tokens: parseInt($('#llm-max-tokens').val())
        },
        flow_control: {
            max_reader_search_attempts: parseInt($('#max-reader-search-attempts').val()),
            max_verifier_rejections: parseInt($('#max-verifier-rejections').val()),
            status_sleep_time: parseFloat($('#status-sleep-time').val())
        },
        docstring_options: {
            overwrite_docstrings: $('#overwrite-docstrings').is(':checked')
        }
    };

    // Add provider-specific fields
    if (llmType === 'bedrock') {
        config.llm.aws_region = $('#aws-region').val();
        const accessKey = $('#aws-access-key').val();
        const secretKey = $('#aws-secret-key').val();

        // Only include credentials if provided
        if (accessKey) {
            config.llm.aws_access_key = accessKey;
        }
        if (secretKey) {
            config.llm.aws_secret_key = secretKey;
        }
    } else {
        config.llm.api_key = $('#llm-api-key').val();
    }

    return config;
} 