/**
 * RATS Main Application
 * Orchestrates the application workflow
 */

class RATSApp {
    constructor() {
        this.currentEnvironment = 'Prod';
        this.currentDevice = null;
        this.currentExecution = null;
        this.executionPoll = null;
        this.init();
    }

    async init() {
        console.log('Initializing RATS Application...');
        
        try {
            // Check API connectivity
            const health = await api.getHealth();
            console.log('API Health Check:', health);
            
            // Load initial data
            await this.loadDevices();
            await this.loadTestConfiguration();
            
            console.log('RATS Application initialized successfully');
        } catch (error) {
            console.error('Failed to initialize RATS Application:', error);
            ui.showStatusModal();
        }
    }

    async loadDevices() {
        try {
            const data = await api.getDevices();
            ui.populateDevices(data.devices);
            console.log(`Loaded ${data.devices.length} devices`);
        } catch (error) {
            console.error('Failed to load devices:', error);
        }
    }

    async loadDeviceInfo(deviceId) {
        if (!deviceId) {
            this.currentDevice = null;
            return;
        }

        try {
            const device = await api.getDevice(deviceId);
            this.currentDevice = device;
            ui.displayDeviceInfo(device);
        } catch (error) {
            console.error('Failed to load device info:', error);
        }
    }

    async loadTestConfiguration() {
        try {
            const groups = await api.getTestGroups();
            ui.populateTestGroups(groups.groups);
            
            const tests = await api.getTests();
            ui.populateTestCases(tests.tests);
            
            console.log(`Loaded ${tests.tests.length} tests from ${groups.groups.length} groups`);
        } catch (error) {
            console.error('Failed to load test configuration:', error);
        }
    }

    filterTestsByGroup() {
        // Get selected groups
        const groupCheckboxes = document.querySelectorAll('.test-group-checkbox:checked');
        const selectedGroups = Array.from(groupCheckboxes).map(cb => cb.value);

        // Filter test items
        const testItems = document.querySelectorAll('.test-case-item');
        testItems.forEach(item => {
            const checkbox = item.querySelector('input');
            const testId = checkbox.value;
            
            // For now, show all tests. In a real app, filter by group
            item.style.display = 'block';
        });
    }

    async startTests() {
        if (!this.currentDevice) {
            alert('Please select a device first');
            return;
        }

        const selectedTests = ui.getSelectedTests();
        if (selectedTests.length === 0) {
            alert('Please select at least one test');
            return;
        }

        try {
            // Start test execution
            const result = await api.executeTests(
                this.currentDevice.id,
                selectedTests
            );

            this.currentExecution = {
                id: result.execution_id,
                device_id: this.currentDevice.id,
                tests: selectedTests,
                completed: 0,
                status: 'running'
            };

            console.log('Tests execution started:', result);

            // Show execution progress
            ui.showExecutionProgress();
            ui.clearTestResults();

            // Start polling for results
            this.pollExecutionProgress();

        } catch (error) {
            console.error('Failed to start tests:', error);
            alert('Failed to start tests: ' + error.message);
        }
    }

    pollExecutionProgress() {
        if (!this.currentExecution) return;

        // Poll every 2 seconds
        this.executionPoll = setInterval(async () => {
            try {
                const data = await api.getExecution(this.currentExecution.id);
                const execution = data.execution;
                const summary = data.summary;

                // Update progress
                ui.updateProgress(
                    summary.total_tests - summary.failed - summary.passed > 0 
                        ? summary.passed + summary.failed
                        : summary.total_tests,
                    summary.total_tests
                );

                // Check if execution is complete
                if (execution.status === 'completed') {
                    clearInterval(this.executionPoll);
                    this.displayExecutionResults(summary);
                }

            } catch (error) {
                console.error('Failed to poll execution progress:', error);
            }
        }, 2000);
    }

    async displayExecutionResults(summary) {
        console.log('Execution Summary:', summary);

        // Update status
        document.getElementById('execution-status').textContent = 'Completed';

        // Display results
        try {
            const data = await api.getExecutionResults(this.currentExecution.id);
            
            data.results.forEach(result => {
                ui.addTestResult(
                    result.test_id,
                    result.passed,
                    result.output,
                    result.errors
                );
            });

            // Show summary
            const summaryDiv = document.createElement('div');
            summaryDiv.classList.add('execution-summary');
            summaryDiv.innerHTML = `
                <h3>Execution Summary</h3>
                <p>Total Tests: ${summary.total_tests}</p>
                <p>Passed: <span class="passed">${summary.passed}</span></p>
                <p>Failed: <span class="failed">${summary.failed}</span></p>
                <p>Pass Rate: ${summary.pass_rate.toFixed(2)}%</p>
                <p>Duration: ${summary.duration ? summary.duration.toFixed(2) + 's' : 'N/A'}</p>
            `;
            ui.testResultsContainer.appendChild(summaryDiv);

        } catch (error) {
            console.error('Failed to display results:', error);
        }
    }

    setEnvironment(env) {
        this.currentEnvironment = env;
        console.log('Environment changed to:', env);
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.app = new RATSApp();
});
