/**
 * DeQ - Main Application Module
 * Handles application state, event binding, and coordination
 */

const App = {
    // Application state
    config: null,
    statusCache: {},
    runningTasks: {},
    editMode: false,
    linkLayout: 'eco',
    monoIcons: false,
    hiddenSections: {},
    pollInterval: null,
    
    // File manager state
    fm: {
        leftDevice: null,
        rightDevice: null,
        leftPath: '/',
        rightPath: '/',
        leftSelected: [],
        rightSelected: [],
        activePane: 'left'
    },

    // ===== INITIALIZATION =====

    /**
     * Initialize the application
     */
    async init() {
        console.log('DeQ initializing...');
        
        // Load config
        await this.loadConfig();
        
        // Bind events
        this.bindEvents();
        
        // Apply theme
        if (this.config?.settings) {
            UI.applyTheme(this.config.settings);
            UI.loadThemeInputs(this.config.settings);
        }
        
        // Load saved preferences
        this.loadPreferences();
        
        // Initial render
        this.render();
        
        // Start status polling
        this.startPolling();
        
        // Check for onboarding
        if (window.NEEDS_ONBOARDING) {
            this.startOnboarding();
        }
        
        // Load version
        this.loadVersion();
        
        console.log('DeQ ready');
    },

    /**
     * Load configuration from server
     */
    async loadConfig() {
        try {
            const result = await API.getConfig();
            this.config = result.config;
            this.runningTasks = result.running_tasks || {};
            return this.config;
        } catch (error) {
            console.error('Failed to load config:', error);
            UI.toast('Failed to load configuration', 'error');
        }
    },

    /**
     * Save configuration to server
     */
    async saveConfig() {
        try {
            await API.saveConfig(this.config);
            UI.toast('Saved', 'success');
            return true;
        } catch (error) {
            console.error('Failed to save config:', error);
            UI.toast('Failed to save', 'error');
            return false;
        }
    },

    /**
     * Load user preferences from localStorage
     */
    loadPreferences() {
        this.linkLayout = localStorage.getItem('deq_link_layout') || 'eco';
        this.monoIcons = localStorage.getItem('deq_mono_icons') === 'true';
        this.hiddenSections = JSON.parse(localStorage.getItem('deq_hidden_sections') || '{}');
        
        // Update layout button
        const layoutLabel = document.getElementById('link-layout-label');
        if (layoutLabel) layoutLabel.textContent = this.linkLayout;
    },

    /**
     * Save user preferences
     */
    savePreferences() {
        localStorage.setItem('deq_link_layout', this.linkLayout);
        localStorage.setItem('deq_mono_icons', this.monoIcons);
        localStorage.setItem('deq_hidden_sections', JSON.stringify(this.hiddenSections));
    },

    // ===== RENDERING =====

    /**
     * Render all sections
     */
    render() {
        UI.renderLinks(this.config?.links, this.editMode, this.linkLayout, this.monoIcons);
        UI.renderDevices(this.config?.devices, this.statusCache, this.editMode);
        UI.renderTasks(this.config?.tasks, this.runningTasks, this.editMode);
        UI.updateSectionVisibility(this.hiddenSections);
        
        // Update edit mode class
        document.body.classList.toggle('edit-mode', this.editMode);
    },

    // ===== EVENT BINDING =====

    /**
     * Bind all event handlers
     */
    bindEvents() {
        // Edit mode toggle
        const editToggle = document.getElementById('edit-toggle');
        if (editToggle) {
            editToggle.onclick = () => this.toggleEditMode();
        }

        // File manager button
        const filesBtn = document.getElementById('files-btn');
        if (filesBtn) {
            filesBtn.onclick = () => this.openFileManager();
        }

        // Add buttons
        document.getElementById('add-link')?.addEventListener('click', () => this.addLink());
        document.getElementById('add-device')?.addEventListener('click', () => this.addDevice());

        // Modal close buttons
        document.querySelectorAll('.modal-close').forEach(btn => {
            btn.onclick = () => UI.hideAllModals();
        });

        // Click outside modal to close
        document.querySelectorAll('.modal').forEach(modal => {
            modal.onclick = (e) => {
                if (e.target === modal) UI.hideAllModals();
            };
        });

        // Theme inputs
        this.bindThemeInputs();

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') UI.hideAllModals();
        });

        // Drag and drop for links and devices
        this.bindDragDrop();
    },

    /**
     * Bind theme input events
     */
    bindThemeInputs() {
        const themeInputs = ['bg', 'cards', 'border', 'text', 'text-muted', 'accent'];
        
        themeInputs.forEach(name => {
            const colorInput = document.getElementById(`theme-${name}`);
            const hexInput = document.getElementById(`theme-${name}-hex`);
            
            if (colorInput) {
                colorInput.oninput = (e) => {
                    if (hexInput) hexInput.value = e.target.value;
                    this.updateThemeFromInputs();
                };
            }
            
            if (hexInput) {
                hexInput.oninput = (e) => {
                    if (colorInput && /^#[0-9A-Fa-f]{6}$/.test(e.target.value)) {
                        colorInput.value = e.target.value;
                        this.updateThemeFromInputs();
                    }
                };
            }
        });

        // Sliders
        const glassSlider = document.getElementById('theme-glass');
        const blurSlider = document.getElementById('theme-blur');
        const wallpaperInput = document.getElementById('theme-wallpaper');

        if (glassSlider) {
            glassSlider.oninput = (e) => {
                document.getElementById('theme-glass-value').textContent = e.target.value + '%';
                this.updateThemeFromInputs();
            };
        }

        if (blurSlider) {
            blurSlider.oninput = (e) => {
                document.getElementById('theme-blur-value').textContent = e.target.value + 'px';
                this.updateThemeFromInputs();
            };
        }

        if (wallpaperInput) {
            wallpaperInput.onchange = () => this.updateThemeFromInputs();
        }
    },

    /**
     * Update theme from input values
     */
    updateThemeFromInputs() {
        const settings = {
            bg_primary: document.getElementById('theme-bg')?.value,
            bg_secondary: document.getElementById('theme-cards')?.value,
            border: document.getElementById('theme-border')?.value,
            text_color: document.getElementById('theme-text')?.value,
            text_muted: document.getElementById('theme-text-muted')?.value,
            accent_color: document.getElementById('theme-accent')?.value,
            glass: parseInt(document.getElementById('theme-glass')?.value) || 0,
            blur: parseInt(document.getElementById('theme-blur')?.value) || 0,
            wallpaper: document.getElementById('theme-wallpaper')?.value || ''
        };

        UI.applyTheme(settings);
        
        // Save to config
        this.config.settings = { ...this.config.settings, ...settings };
        this.saveConfig();
    },

    /**
     * Reset theme to defaults
     */
    resetTheme() {
        const defaults = {
            bg_primary: '#161616',
            bg_secondary: '#151515',
            border: '#2b2b2b',
            text_color: '#e0e0e0',
            text_muted: '#b6b6b6',
            accent_color: '#2ed573',
            glass: 0,
            blur: 0,
            wallpaper: ''
        };

        this.config.settings = { ...this.config.settings, ...defaults };
        UI.applyTheme(defaults);
        UI.loadThemeInputs(defaults);
        this.saveConfig();
        UI.toast('Theme reset', 'success');
    },

    /**
     * Bind drag and drop events
     */
    bindDragDrop() {
        // Will be re-bound after render in edit mode
    },

    // ===== EDIT MODE =====

    /**
     * Toggle edit mode
     */
    toggleEditMode() {
        this.editMode = !this.editMode;
        document.getElementById('edit-toggle')?.classList.toggle('active', this.editMode);
        this.render();
    },

    // ===== LINKS =====

    /**
     * Add new link
     */
    addLink() {
        this.openLinkModal();
    },

    /**
     * Edit existing link
     */
    editLink(index) {
        this.openLinkModal(index);
    },

    /**
     * Open link modal
     */
    openLinkModal(index = null) {
        const isEdit = index !== null;
        const link = isEdit ? this.config.links[index] : {};

        const modal = document.getElementById('link-modal');
        if (!modal) return;

        document.getElementById('link-modal-title').textContent = isEdit ? 'Edit Link' : 'Add Link';
        document.getElementById('link-name').value = link.name || '';
        document.getElementById('link-url').value = link.url || '';
        document.getElementById('link-icon').value = link.icon || 'link';
        document.getElementById('link-icon-url').value = link.icon_url || '';

        // Store index for save
        modal.dataset.index = index ?? '';

        UI.showModal('link-modal');
    },

    /**
     * Save link from modal
     */
    saveLink() {
        const modal = document.getElementById('link-modal');
        const index = modal.dataset.index;
        
        const link = {
            id: index ? this.config.links[index].id : UI.generateId(),
            name: document.getElementById('link-name').value.trim(),
            url: document.getElementById('link-url').value.trim(),
            icon: document.getElementById('link-icon').value || 'link',
            icon_url: document.getElementById('link-icon-url').value.trim()
        };

        if (!link.name || !link.url) {
            UI.toast('Name and URL are required', 'error');
            return;
        }

        if (index !== '') {
            this.config.links[parseInt(index)] = link;
        } else {
            this.config.links.push(link);
        }

        this.saveConfig();
        this.render();
        UI.hideModal('link-modal');
    },

    /**
     * Delete link
     */
    deleteLink(index) {
        if (!confirm('Delete this link?')) return;
        this.config.links.splice(index, 1);
        this.saveConfig();
        this.render();
    },

    /**
     * Cycle link layout
     */
    cycleLinkLayout() {
        const layouts = ['eco', '1-4', '2-4', '4-4'];
        const currentIndex = layouts.indexOf(this.linkLayout);
        this.linkLayout = layouts[(currentIndex + 1) % layouts.length];
        
        document.getElementById('link-layout-label').textContent = this.linkLayout;
        this.savePreferences();
        this.render();
    },

    /**
     * Toggle monochrome icons
     */
    toggleMonochrome() {
        this.monoIcons = !this.monoIcons;
        this.savePreferences();
        this.render();
    },

    // ===== DEVICES =====

    /**
     * Add new device
     */
    addDevice() {
        this.openDeviceModal();
    },

    /**
     * Edit existing device
     */
    editDevice(index) {
        this.openDeviceModal(index);
    },

    /**
     * Open device modal
     */
    openDeviceModal(index = null) {
        const isEdit = index !== null;
        const device = isEdit ? this.config.devices[index] : {};

        const modal = document.getElementById('device-modal');
        if (!modal) return;

        document.getElementById('device-modal-title').textContent = isEdit ? 'Edit Device' : 'Add Device';
        document.getElementById('device-name').value = device.name || '';
        document.getElementById('device-ip').value = device.ip || '';
        document.getElementById('device-icon').value = device.icon || 'server';
        document.getElementById('device-mac').value = device.mac || '';
        document.getElementById('device-ssh-user').value = device.ssh_user || '';
        document.getElementById('device-ssh-port').value = device.ssh_port || 22;

        modal.dataset.index = index ?? '';

        UI.showModal('device-modal');
    },

    /**
     * Save device from modal
     */
    saveDevice() {
        const modal = document.getElementById('device-modal');
        const index = modal.dataset.index;
        
        const device = {
            id: index ? this.config.devices[index].id : UI.generateId(),
            name: document.getElementById('device-name').value.trim(),
            ip: document.getElementById('device-ip').value.trim(),
            icon: document.getElementById('device-icon').value || 'server',
            mac: document.getElementById('device-mac').value.trim(),
            ssh_user: document.getElementById('device-ssh-user').value.trim(),
            ssh_port: parseInt(document.getElementById('device-ssh-port').value) || 22
        };

        // Preserve existing data
        if (index !== '') {
            const existing = this.config.devices[parseInt(index)];
            device.is_host = existing.is_host;
            device.containers = existing.containers;
        }

        if (!device.name || !device.ip) {
            UI.toast('Name and IP are required', 'error');
            return;
        }

        if (index !== '') {
            this.config.devices[parseInt(index)] = device;
        } else {
            this.config.devices.push(device);
        }

        this.saveConfig();
        this.render();
        UI.hideModal('device-modal');
        
        // Refresh status for new device
        this.refreshDeviceStatus(device.id);
    },

    /**
     * Delete device
     */
    deleteDevice(index) {
        const device = this.config.devices[index];
        if (device.is_host) {
            UI.toast('Cannot delete host device', 'error');
            return;
        }
        if (!confirm(`Delete "${device.name}"?`)) return;
        
        this.config.devices.splice(index, 1);
        this.saveConfig();
        this.render();
    },

    // ===== DEVICE ACTIONS =====

    /**
     * Wake device via WOL
     */
    async wakeDevice(deviceId) {
        try {
            const result = await API.wakeDevice(deviceId);
            if (result.success) {
                UI.toast('Wake packet sent', 'success');
            } else {
                UI.toast(result.error || 'Failed to wake device', 'error');
            }
        } catch (error) {
            UI.toast('Failed to wake device', 'error');
        }
    },

    /**
     * Shutdown device
     */
    async shutdownDevice(deviceId) {
        if (!confirm('Shutdown this device?')) return;
        
        try {
            const result = await API.shutdownDevice(deviceId);
            if (result.success) {
                UI.toast('Shutdown command sent', 'success');
                this.statusCache[deviceId] = { online: false };
                this.render();
            } else {
                UI.toast(result.error || 'Failed to shutdown', 'error');
            }
        } catch (error) {
            UI.toast('Failed to shutdown', 'error');
        }
    },

    /**
     * Toggle stats view (bars vs numbers)
     */
    toggleStatsView(element) {
        element.classList.toggle('show-values');
    },

    /**
     * Toggle containers list
     */
    toggleContainers(deviceId) {
        const list = document.getElementById(`containers-${deviceId}`);
        const chevron = document.getElementById(`chevron-${deviceId}`);
        
        if (list) list.classList.toggle('expanded');
        if (chevron) chevron.classList.toggle('expanded');
    },

    /**
     * Docker container action
     */
    async dockerAction(deviceId, containerName, action) {
        const spinnerId = `spinner-${deviceId}-${containerName}`;
        const spinner = document.getElementById(spinnerId);
        if (spinner) spinner.classList.add('active');

        try {
            const result = await API.dockerAction(deviceId, containerName, action);
            if (result.success) {
                UI.toast(`Container ${action}ed`, 'success');
                // Refresh device to get updated container status
                await this.refreshDeviceStatus(deviceId);
            } else {
                UI.toast(result.error || `Failed to ${action} container`, 'error');
            }
        } catch (error) {
            UI.toast(`Failed to ${action} container`, 'error');
        } finally {
            if (spinner) spinner.classList.remove('active');
        }
    },

    /**
     * Show detailed stats modal
     */
    async showStatsModal(deviceId) {
        // TODO: Implement stats modal
        const device = this.config.devices.find(d => d.id === deviceId);
        if (!device) return;

        try {
            const result = await API.getDeviceStats(deviceId);
            if (result.success) {
                // Show modal with stats
                console.log('Stats:', result.stats);
                UI.toast('Stats loaded', 'success');
            }
        } catch (error) {
            UI.toast('Failed to load stats', 'error');
        }
    },

    // ===== STATUS POLLING =====

    /**
     * Start status polling
     */
    startPolling() {
        // Initial fetch
        this.pollStatus();
        
        // Poll every 30 seconds
        this.pollInterval = setInterval(() => this.pollStatus(), 30000);
    },

    /**
     * Stop status polling
     */
    stopPolling() {
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
        }
    },

    /**
     * Poll all device statuses
     */
    async pollStatus() {
        if (!this.config?.devices) return;

        for (const device of this.config.devices) {
            this.refreshDeviceStatus(device.id);
        }
    },

    /**
     * Refresh single device status
     */
    async refreshDeviceStatus(deviceId) {
        try {
            // Mark as loading
            this.statusCache[deviceId] = { ...this.statusCache[deviceId], loading: true };
            
            const result = await API.getDeviceStatus(deviceId);
            
            this.statusCache[deviceId] = {
                online: result.online,
                stats: result.stats || {},
                loading: false
            };

            // Update containers if online
            if (result.containers) {
                const device = this.config.devices.find(d => d.id === deviceId);
                if (device) {
                    device.containers = result.containers;
                }
            }

            this.render();
        } catch (error) {
            this.statusCache[deviceId] = { online: false, loading: false };
            this.render();
        }
    },

    // ===== TASKS =====

    /**
     * Open task wizard
     */
    openTaskWizard(index = null) {
        // TODO: Implement task wizard
        UI.showModal('task-modal');
    },

    /**
     * Edit task
     */
    editTask(index) {
        this.openTaskWizard(index);
    },

    /**
     * Delete task
     */
    deleteTask(index) {
        const task = this.config.tasks[index];
        if (!confirm(`Delete task "${task.name}"?`)) return;
        
        this.config.tasks.splice(index, 1);
        this.saveConfig();
        this.render();
    },

    /**
     * Run task manually
     */
    async runTask(taskId) {
        try {
            const result = await API.runTask(taskId);
            if (result.success) {
                UI.toast('Task started', 'success');
                this.runningTasks[taskId] = true;
                this.render();
            } else {
                UI.toast(result.error || 'Failed to run task', 'error');
            }
        } catch (error) {
            UI.toast('Failed to run task', 'error');
        }
    },

    /**
     * Toggle task enabled state
     */
    async toggleTask(taskId) {
        const task = this.config.tasks.find(t => t.id === taskId);
        if (!task) return;

        task.enabled = !task.enabled;
        await this.saveConfig();
        this.render();
    },

    // ===== SECTIONS =====

    /**
     * Toggle section visibility
     */
    toggleSection(section) {
        this.hiddenSections[section] = !this.hiddenSections[section];
        this.savePreferences();
        UI.updateSectionVisibility(this.hiddenSections);
    },

    // ===== FILE MANAGER =====

    /**
     * Open file manager
     */
    openFileManager() {
        UI.showModal('file-manager-modal');
        
        // Initialize with first device
        if (this.config?.devices?.length > 0) {
            this.fm.leftDevice = this.config.devices[0].id;
            this.fm.rightDevice = this.config.devices[0].id;
            this.loadFilePane('left');
            this.loadFilePane('right');
        }
    },

    /**
     * Load file pane
     */
    async loadFilePane(pane) {
        const deviceId = pane === 'left' ? this.fm.leftDevice : this.fm.rightDevice;
        const path = pane === 'left' ? this.fm.leftPath : this.fm.rightPath;

        if (!deviceId) return;

        try {
            const result = await API.browse(deviceId, path);
            if (result.success) {
                UI.renderFileList(pane, result.files, path);
                
                // Update storage info if available
                if (result.storage) {
                    this.updateStorageInfo(pane, result.storage);
                }
            }
        } catch (error) {
            UI.toast('Failed to load directory', 'error');
        }
    },

    /**
     * Update storage info in file manager
     */
    updateStorageInfo(pane, storage) {
        const fill = document.querySelector(`#fm-pane-${pane} .fm-storage-fill`);
        const percent = document.querySelector(`#fm-pane-${pane} .fm-storage-percent`);
        const text = document.querySelector(`#fm-pane-${pane} .fm-storage-text`);

        if (fill) {
            fill.style.width = storage.percent + '%';
            fill.style.background = storage.percent > 90 ? 'var(--danger)' : 'var(--accent)';
        }
        if (percent) percent.textContent = storage.percent + '%';
        if (text) text.textContent = `${UI.formatSize(storage.used)} / ${UI.formatSize(storage.total)}`;
    },

    // ===== ONBOARDING =====

    /**
     * Start onboarding wizard
     */
    async startOnboarding(scanOnly = false) {
        UI.showModal('onboarding-modal');
        
        if (!scanOnly) {
            // Show scanning state
            document.getElementById('onboarding-content').innerHTML = `
                <div style="text-align: center; padding: 40px;">
                    <div class="container-spinner active" style="margin: 0 auto 16px; display: block;"></div>
                    <p>Scanning network...</p>
                </div>
            `;
        }

        try {
            const result = await API.scanNetwork();
            if (result.success) {
                this.renderOnboardingResults(result.devices);
            }
        } catch (error) {
            UI.toast('Network scan failed', 'error');
        }
    },

    /**
     * Render onboarding scan results
     */
    renderOnboardingResults(devices) {
        const content = document.getElementById('onboarding-content');
        if (!content) return;

        content.innerHTML = `
            <div class="onboarding-header">
                <span></span>
                <span>Name</span>
                <span>IP</span>
                <span>Status</span>
            </div>
            ${devices.map(device => `
                <div class="onboarding-row">
                    <input type="checkbox" ${device.reachable ? 'checked' : ''} data-ip="${device.ip}">
                    <input type="text" value="${device.hostname || device.ip}" class="ob-name">
                    <span class="ob-ip">${device.ip}</span>
                    <span class="ob-status ${device.reachable ? 'online' : ''}"></span>
                </div>
            `).join('')}
        `;
    },

    /**
     * Complete onboarding
     */
    async completeOnboarding() {
        const rows = document.querySelectorAll('#onboarding-content .onboarding-row');
        const newDevices = [];

        rows.forEach(row => {
            const checkbox = row.querySelector('input[type="checkbox"]');
            if (checkbox?.checked) {
                const name = row.querySelector('.ob-name')?.value || checkbox.dataset.ip;
                newDevices.push({
                    id: UI.generateId(),
                    name: name,
                    ip: checkbox.dataset.ip,
                    icon: 'server'
                });
            }
        });

        if (newDevices.length > 0) {
            this.config.devices.push(...newDevices);
            await this.saveConfig();
        }

        await API.completeOnboarding();
        UI.hideModal('onboarding-modal');
        this.render();
        this.pollStatus();
    },

    // ===== MISC =====

    /**
     * Load and display version
     */
    async loadVersion() {
        try {
            const result = await API.getVersion();
            const versionEl = document.getElementById('version');
            if (versionEl && result.version) {
                versionEl.textContent = 'v' + result.version;
            }
        } catch (error) {
            console.log('Could not load version');
        }
    }
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    App.init();
});

// Make App globally available
window.App = App;
