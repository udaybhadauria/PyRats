/**
 * RATS UI Module
 * Handles DOM manipulation and UI updates
 */

class RATSUi {
    constructor() {
        this.deviceSelect = document.getElementById('device-select');
        this.testGroupsContainer = document.getElementById('test-groups');
        this.testCasesContainer = document.getElementById('test-cases');
        this.executionSection = document.getElementById('execution-section');
        this.progressBar = document.getElementById('progress-bar');
        this.progressText = document.getElementById('progress-text');
        this.testResultsContainer = document.getElementById('test-results');
        this.statusModal = document.getElementById('status-modal');
        this.setupEventListeners();
    }

    setupEventListeners() {
        // Device selection
        this.deviceSelect.addEventListener('change', (e) => {
            this.onDeviceSelected(e.target.value);
        });

        // Test control buttons
        document.getElementById('refresh-devices').addEventListener('click', () => {
            window.app.loadDevices();
        });

        document.getElementById('select-all-btn').addEventListener('click', () => {
            this.selectAllTests();
        });

        document.getElementById('deselect-all-btn').addEventListener('click', () => {
            this.deselectAllTests();
        });

        document.getElementById('start-tests-btn').addEventListener('click', () => {
            window.app.startTests();
        });

        // Status modal
        document.getElementById('status-btn').addEventListener('click', () => {
            this.showStatusModal();
        });

        document.querySelector('.modal .close').addEventListener('click', () => {
            this.hideStatusModal();
        });

        // Environment selector
        document.getElementById('env-select').addEventListener('change', (e) => {
            window.app.setEnvironment(e.target.value);
        });
    }

    populateDevices(devices) {
        this.deviceSelect.innerHTML = '<option value="">-- Select a device --</option>';
        
        devices.forEach(device => {
            const option = document.createElement('option');
            option.value = device.id;
            option.textContent = `${device.name} (${device.mac_address})`;
            option.dataset.status = device.status;
            this.deviceSelect.appendChild(option);
        });
    }

    populateTestGroups(groups) {
        this.testGroupsContainer.innerHTML = '';
        
        groups.forEach(group => {
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.id = `group-${group}`;
            checkbox.value = group;
            checkbox.classList.add('test-group-checkbox');
            
            const label = document.createElement('label');
            label.htmlFor = checkbox.id;
            label.textContent = group;
            
            const container = document.createElement('div');
            container.classList.add('test-group-item');
            container.appendChild(checkbox);
            container.appendChild(label);
            
            this.testGroupsContainer.appendChild(container);
            
            checkbox.addEventListener('change', () => {
                window.app.filterTestsByGroup();
            });
        });
    }

    populateTestCases(tests) {
        this.testCasesContainer.innerHTML = '';
        
        tests.forEach(test => {
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.id = `test-${test.id}`;
            checkbox.value = test.id;
            checkbox.classList.add('test-case-checkbox');
            
            const label = document.createElement('label');
            label.htmlFor = checkbox.id;
            label.innerHTML = `
                <strong>${test.name}</strong>
                <small>${test.description || ''}</small>
            `;
            
            const container = document.createElement('div');
            container.classList.add('test-case-item');
            container.appendChild(checkbox);
            container.appendChild(label);
            
            this.testCasesContainer.appendChild(container);
        });
    }

    selectAllTests() {
        const checkboxes = this.testCasesContainer.querySelectorAll('input[type="checkbox"]');
        checkboxes.forEach(cb => cb.checked = true);
    }

    deselectAllTests() {
        const checkboxes = this.testCasesContainer.querySelectorAll('input[type="checkbox"]');
        checkboxes.forEach(cb => cb.checked = false);
    }

    getSelectedTests() {
        const checkboxes = this.testCasesContainer.querySelectorAll('input[type="checkbox"]:checked');
        return Array.from(checkboxes).map(cb => cb.value);
    }

    showExecutionProgress() {
        this.executionSection.classList.remove('hidden');
        window.scrollTo({ top: this.executionSection.offsetTop, behavior: 'smooth' });
    }

    updateProgress(completed, total) {
        const percentage = (completed / total) * 100;
        this.progressBar.style.width = `${percentage}%`;
        this.progressText.textContent = `${completed} of ${total} tests completed`;
    }

    addTestResult(testName, passed, output = '', errors = []) {
        const resultDiv = document.createElement('div');
        resultDiv.classList.add('test-result', passed ? 'passed' : 'failed');
        resultDiv.innerHTML = `
            <div class="test-result-header">
                <span class="test-name">${testName}</span>
                <span class="test-status">${passed ? '✓ PASSED' : '✗ FAILED'}</span>
            </div>
            ${output ? `<div class="test-output"><pre>${output}</pre></div>` : ''}
            ${errors.length > 0 ? `<div class="test-errors"><strong>Errors:</strong><ul>${errors.map(e => `<li>${e}</li>`).join('')}</ul></div>` : ''}
        `;
        this.testResultsContainer.appendChild(resultDiv);
    }

    clearTestResults() {
        this.testResultsContainer.innerHTML = '';
    }

    onDeviceSelected(deviceId) {
        // This will be overridden by the main app
        if (window.app) {
            window.app.loadDeviceInfo(deviceId);
        }
    }

    displayDeviceInfo(device) {
        const deviceInfo = document.getElementById('device-info');
        const deviceDetails = document.getElementById('device-details');
        const deviceStatus = document.getElementById('device-status');

        deviceStatus.textContent = device.status || 'Unknown';
        deviceStatus.className = `device-status ${device.status || 'unknown'}`;

        deviceDetails.innerHTML = `
            <p><strong>Name:</strong> ${device.name}</p>
            <p><strong>MAC Address:</strong> ${device.mac_address}</p>
            <p><strong>IP Address:</strong> ${device.ip_address || 'N/A'}</p>
            <p><strong>Type:</strong> ${device.device_type}</p>
            <p><strong>Location:</strong> ${device.location || 'N/A'}</p>
        `;

        deviceInfo.classList.remove('hidden');
    }

    async showStatusModal() {
        try {
            const health = await api.getHealth();
            const statusDetails = document.getElementById('status-details');
            
            statusDetails.innerHTML = `
                <div class="status-item">
                    <strong>Overall Status:</strong> <span class="status-${health.services.mqtt}">${health.services.mqtt.toUpperCase()}</span>
                </div>
                <div class="status-item">
                    <strong>MQTT Broker:</strong> <span class="status-${health.services.mqtt}">${health.services.mqtt.toUpperCase()}</span>
                </div>
                <div class="status-item">
                    <strong>API Server:</strong> <span class="status-connected">${health.services.api.toUpperCase()}</span>
                </div>
            `;
            
            this.statusModal.classList.remove('hidden');
        } catch (error) {
            console.error('Failed to fetch health status:', error);
        }
    }

    hideStatusModal() {
        this.statusModal.classList.add('hidden');
    }
}

// Create global UI instance when DOM is ready
const ui = new RATSUi();
