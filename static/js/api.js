/**
 * DeQ - API Module
 * Handles all HTTP API calls to the backend
 */

const API = {
    /**
     * Make an API request
     * @param {string} endpoint - API endpoint
     * @param {object} options - Fetch options
     * @returns {Promise<object>}
     */
    async request(endpoint, options = {}) {
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };

        // Add API key if stored
        const apiKey = localStorage.getItem('deq_api_key');
        if (apiKey) {
            config.headers['X-API-Key'] = apiKey;
        }

        try {
            const response = await fetch(endpoint, config);
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || `HTTP ${response.status}`);
            }
            
            return data;
        } catch (error) {
            console.error(`API Error [${endpoint}]:`, error);
            throw error;
        }
    },

    /**
     * GET request
     * @param {string} endpoint
     * @returns {Promise<object>}
     */
    get(endpoint) {
        return this.request(endpoint, { method: 'GET' });
    },

    /**
     * POST request
     * @param {string} endpoint
     * @param {object} data
     * @returns {Promise<object>}
     */
    post(endpoint, data) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    // ===== CONFIG =====
    
    /**
     * Get full configuration
     * @returns {Promise<object>}
     */
    async getConfig() {
        const result = await this.get('/api/config');
        return result;
    },

    /**
     * Save configuration
     * @param {object} config
     * @returns {Promise<object>}
     */
    saveConfig(config) {
        return this.post('/api/config', config);
    },

    // ===== DEVICES =====

    /**
     * Get device status
     * @param {string} deviceId
     * @returns {Promise<object>}
     */
    getDeviceStatus(deviceId) {
        return this.get(`/api/device/${deviceId}/status`);
    },

    /**
     * Get device stats
     * @param {string} deviceId
     * @returns {Promise<object>}
     */
    getDeviceStats(deviceId) {
        return this.get(`/api/device/${deviceId}/stats`);
    },

    /**
     * Wake device (WOL)
     * @param {string} deviceId
     * @returns {Promise<object>}
     */
    wakeDevice(deviceId) {
        return this.post(`/api/device/${deviceId}/wake`, {});
    },

    /**
     * Shutdown device
     * @param {string} deviceId
     * @returns {Promise<object>}
     */
    shutdownDevice(deviceId) {
        return this.post(`/api/device/${deviceId}/shutdown`, {});
    },

    /**
     * Check SSH access
     * @param {string} deviceId
     * @returns {Promise<object>}
     */
    checkSSH(deviceId) {
        return this.get(`/api/device/${deviceId}/ssh-check`);
    },

    /**
     * Scan for containers on device
     * @param {string} deviceId
     * @returns {Promise<object>}
     */
    scanContainers(deviceId) {
        return this.get(`/api/device/${deviceId}/containers`);
    },

    // ===== DOCKER =====

    /**
     * Perform docker action
     * @param {string} deviceId
     * @param {string} container
     * @param {string} action - start, stop, restart
     * @returns {Promise<object>}
     */
    dockerAction(deviceId, container, action) {
        return this.post(`/api/device/${deviceId}/docker`, {
            container,
            action
        });
    },

    /**
     * Get container logs
     * @param {string} deviceId
     * @param {string} container
     * @param {number} lines
     * @returns {Promise<object>}
     */
    getContainerLogs(deviceId, container, lines = 100) {
        return this.get(`/api/device/${deviceId}/docker/logs?container=${encodeURIComponent(container)}&lines=${lines}`);
    },

    // ===== FILES =====

    /**
     * Browse directory
     * @param {string} deviceId
     * @param {string} path
     * @returns {Promise<object>}
     */
    browse(deviceId, path) {
        return this.get(`/api/device/${deviceId}/browse?path=${encodeURIComponent(path)}`);
    },

    /**
     * List files
     * @param {string} deviceId
     * @param {string} path
     * @returns {Promise<object>}
     */
    listFiles(deviceId, path) {
        return this.get(`/api/device/${deviceId}/files?path=${encodeURIComponent(path)}`);
    },

    /**
     * File operation (copy, move, delete)
     * @param {object} params
     * @returns {Promise<object>}
     */
    fileOperation(params) {
        return this.post('/api/files/operation', params);
    },

    /**
     * Download file URL
     * @param {string} deviceId
     * @param {string} path
     * @returns {string}
     */
    getDownloadUrl(deviceId, path) {
        return `/api/device/${deviceId}/download?path=${encodeURIComponent(path)}`;
    },

    // ===== TASKS =====

    /**
     * Run a task
     * @param {string} taskId
     * @returns {Promise<object>}
     */
    runTask(taskId) {
        return this.post(`/api/task/${taskId}/run`, {});
    },

    /**
     * Get task status
     * @param {string} taskId
     * @returns {Promise<object>}
     */
    getTaskStatus(taskId) {
        return this.get(`/api/task/${taskId}/status`);
    },

    // ===== NETWORK =====

    /**
     * Scan network for devices
     * @returns {Promise<object>}
     */
    scanNetwork() {
        return this.get('/api/network/scan');
    },

    // ===== HOST =====

    /**
     * Get host stats
     * @returns {Promise<object>}
     */
    getHostStats() {
        return this.get('/api/stats/host');
    },

    // ===== HEALTH =====

    /**
     * Get health status
     * @returns {Promise<object>}
     */
    getHealth() {
        return this.get('/api/health');
    },

    /**
     * Get version info
     * @returns {Promise<object>}
     */
    getVersion() {
        return this.get('/api/version');
    },

    // ===== AUTH =====

    /**
     * Setup API key (first time)
     * @returns {Promise<object>}
     */
    setupAuth() {
        return this.get('/api/auth/setup');
    },

    // ===== ONBOARDING =====

    /**
     * Mark onboarding complete
     * @returns {Promise<object>}
     */
    completeOnboarding() {
        return this.post('/api/onboarding/complete', {});
    },

    // ===== NOTIFICATIONS =====

    /**
     * Get notification settings
     * @returns {Promise<object>}
     */
    getNotificationSettings() {
        return this.get('/api/notifications');
    },

    /**
     * Update notification settings
     * @param {object} settings
     * @returns {Promise<object>}
     */
    updateNotificationSettings(settings) {
        return this.post('/api/notifications', settings);
    },

    /**
     * Test notification
     * @param {string} channel - ntfy, discord, slack, webhook, all
     * @returns {Promise<object>}
     */
    testNotification(channel = 'all') {
        return this.post('/api/notifications/test', { channel });
    }
};

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = API;
}
