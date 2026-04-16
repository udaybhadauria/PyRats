/**
 * RATS API Client
 * Handles all API communication with backend
 */

const API_BASE_URL = 'http://localhost:8888/api';

class RATSApi {
    constructor(baseUrl = API_BASE_URL) {
        this.baseUrl = baseUrl;
        this.executionWs = null;
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };

        try {
            const response = await fetch(url, config);
            
            if (!response.ok) {
                const error = await response.json().catch(() => ({}));
                throw new Error(error.detail || `HTTP ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error(`API Error [${endpoint}]:`, error);
            throw error;
        }
    }

    // Device APIs
    getDevices(status = null) {
        const query = status ? `?status=${status}` : '';
        return this.request(`/devices${query}`);
    }

    getDevice(deviceId) {
        return this.request(`/devices/${deviceId}`);
    }

    createDevice(device) {
        return this.request('/devices', {
            method: 'POST',
            body: JSON.stringify(device)
        });
    }

    updateDevice(deviceId, deviceUpdate) {
        return this.request(`/devices/${deviceId}`, {
            method: 'PUT',
            body: JSON.stringify(deviceUpdate)
        });
    }

    deleteDevice(deviceId) {
        return this.request(`/devices/${deviceId}`, {
            method: 'DELETE'
        });
    }

    getDeviceCount() {
        return this.request('/devices/count');
    }

    // Test APIs
    getTestGroups() {
        return this.request('/tests/groups');
    }

    getTests(group = null) {
        const query = group ? `?group=${group}` : '';
        return this.request(`/tests${query}`);
    }

    executeTests(deviceId, testCases, parameters = {}) {
        return this.request('/tests/execute', {
            method: 'POST',
            body: JSON.stringify({
                device_id: deviceId,
                test_cases: testCases,
                parameters: parameters
            })
        });
    }

    getExecution(executionId) {
        return this.request(`/tests/execution/${executionId}`);
    }

    getExecutionResults(executionId) {
        return this.request(`/tests/execution/${executionId}/results`);
    }

    // Health APIs
    getHealth() {
        return this.request('/health');
    }

    getReadiness() {
        return this.request('/health/ready');
    }

    getLiveness() {
        return this.request('/health/live');
    }
}

// Create global API instance
const api = new RATSApi();
