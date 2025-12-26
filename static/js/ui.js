/**
 * DeQ - UI Module
 * Handles all DOM rendering and UI updates
 */

const UI = {
    // ===== ICONS =====
    icons: {
        // Lucide icon names for devices
        deviceIcons: ['server', 'cpu', 'hard-drive', 'monitor', 'laptop', 'smartphone', 'tablet', 'router', 'wifi', 'database', 'cloud', 'box', 'package', 'terminal', 'code', 'globe', 'home', 'building', 'warehouse'],
        
        // Get Lucide icon HTML
        getIcon(name, className = '') {
            return `<i data-lucide="${name}" class="${className}"></i>`;
        },

        // Get SVG icon (for links with custom URLs)
        getCustomIcon(url, mono = false) {
            const monoClass = mono ? 'mono' : '';
            return `<img src="${url}" class="custom-icon ${monoClass}" onerror="this.style.display='none'">`;
        }
    },

    // ===== TOAST NOTIFICATIONS =====
    
    /**
     * Show toast message
     * @param {string} message
     * @param {string} type - 'success', 'error', or empty
     */
    toast(message, type = '') {
        const toast = document.getElementById('toast');
        if (!toast) return;
        
        toast.textContent = message;
        toast.className = 'toast visible ' + type;
        
        setTimeout(() => {
            toast.classList.remove('visible');
        }, 3000);
    },

    // ===== LINKS =====

    /**
     * Render links grid
     * @param {Array} links
     * @param {boolean} editMode
     * @param {string} layout - 'eco', '1-4', '2-4', '4-4'
     * @param {boolean} mono - Monochrome icons
     */
    renderLinks(links, editMode = false, layout = 'eco', mono = false) {
        const grid = document.getElementById('links-grid');
        if (!grid) return;

        // Set layout class
        grid.className = 'links-grid';
        if (layout !== 'eco') {
            grid.classList.add(`layout-${layout}`);
        }

        if (!links || links.length === 0) {
            grid.innerHTML = editMode ? 
                '<div class="links-empty">Click + to add your first link</div>' : '';
            return;
        }

        grid.innerHTML = links.map((link, index) => {
            const iconHtml = link.icon_url ? 
                `<div class="link-icon ${mono ? 'mono' : ''}">${this.icons.getCustomIcon(link.icon_url, mono)}</div>` :
                `<div class="link-icon">${this.icons.getIcon(link.icon || 'link')}</div>`;

            return `
                <a href="${this.escapeHtml(link.url)}" target="_blank" rel="noopener" 
                   class="link-item" draggable="${editMode}" data-index="${index}">
                    ${iconHtml}
                    <span class="link-name">${this.escapeHtml(link.name)}</span>
                    <button class="link-edit-btn" onclick="event.preventDefault(); App.editLink(${index})">
                        ${this.icons.getIcon('pencil')}
                    </button>
                </a>
            `;
        }).join('');

        // Re-initialize Lucide icons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    },

    // ===== DEVICES =====

    /**
     * Render devices list
     * @param {Array} devices
     * @param {object} statusCache - Cached device statuses
     * @param {boolean} editMode
     */
    renderDevices(devices, statusCache = {}, editMode = false) {
        const list = document.getElementById('devices-list');
        if (!list) return;

        if (!devices || devices.length === 0) {
            list.innerHTML = '<div class="task-empty">No devices configured</div>';
            return;
        }

        list.innerHTML = devices.map((device, index) => {
            const status = statusCache[device.id] || {};
            const isOnline = status.online;
            const stats = status.stats || {};
            
            return this.renderDeviceCard(device, index, status, stats, editMode);
        }).join('');

        // Re-initialize Lucide icons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    },

    /**
     * Render single device card
     */
    renderDeviceCard(device, index, status, stats, editMode) {
        const isOnline = status.online;
        const statusClass = status.loading ? 'loading' : (isOnline ? 'online' : 'offline');
        
        // Stats bars
        const cpu = stats.cpu || 0;
        const ram = stats.ram || 0;
        const temp = stats.temp;
        
        const cpuColor = cpu > 90 ? 'var(--danger)' : cpu > 70 ? 'var(--warning)' : 'var(--accent)';
        const ramColor = ram > 90 ? 'var(--danger)' : ram > 70 ? 'var(--warning)' : 'var(--accent)';

        // Containers section
        let containersHtml = '';
        if (device.containers && device.containers.length > 0) {
            const runningCount = device.containers.filter(c => c.status === 'running').length;
            containersHtml = `
                <div class="device-containers">
                    <div class="containers-toggle" onclick="App.toggleContainers('${device.id}')">
                        <div class="containers-summary">
                            ${this.icons.getIcon('box')}
                            <span>${runningCount}/${device.containers.length}</span>
                        </div>
                        <svg class="containers-chevron" id="chevron-${device.id}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M6 9l6 6 6-6"/>
                        </svg>
                    </div>
                    <div class="containers-list" id="containers-${device.id}">
                        ${device.containers.map(c => this.renderContainerRow(device.id, c)).join('')}
                    </div>
                </div>
            `;
        }

        return `
            <div class="device-card" draggable="${editMode}" data-index="${index}" data-id="${device.id}">
                <div class="device-header">
                    <div class="device-info">
                        <div class="device-icon">${this.icons.getIcon(device.icon || 'server')}</div>
                        <div>
                            <div class="device-name">${this.escapeHtml(device.name)}</div>
                            <div style="font-size: 11px; color: var(--text-secondary)">${device.ip}</div>
                        </div>
                    </div>
                    <div class="status-dot ${statusClass}"></div>
                </div>
                
                ${isOnline ? `
                <div class="device-stats-bars" onclick="App.toggleStatsView(this)">
                    <div class="stat-bar-group">
                        <span class="stat-label">CPU</span>
                        <div class="stat-bar"><div class="stat-bar-fill" style="width: ${cpu}%; background: ${cpuColor}"></div></div>
                        <span class="stat-value">${cpu}%</span>
                    </div>
                    <div class="stat-bar-group">
                        <span class="stat-label">RAM</span>
                        <div class="stat-bar"><div class="stat-bar-fill" style="width: ${ram}%; background: ${ramColor}"></div></div>
                        <span class="stat-value">${ram}%</span>
                    </div>
                    ${temp !== null && temp !== undefined ? `
                    <div class="stat-bar-group">
                        <span class="stat-label">Temp</span>
                        <span class="stat-value" style="display: block">${temp}°C</span>
                    </div>
                    ` : ''}
                    <button class="stats-modal-btn" onclick="event.stopPropagation(); App.showStatsModal('${device.id}')" title="View details">
                        ${this.icons.getIcon('info')}
                    </button>
                </div>
                ` : ''}
                
                <div class="device-actions">
                    ${!isOnline && device.mac ? `
                        <button class="device-action" onclick="App.wakeDevice('${device.id}')" title="Wake on LAN">
                            ${this.icons.getIcon('power')} Wake
                        </button>
                        <span class="action-separator">|</span>
                    ` : ''}
                    ${isOnline && device.ssh_user ? `
                        <button class="device-action danger" onclick="App.shutdownDevice('${device.id}')" title="Shutdown">
                            ${this.icons.getIcon('power-off')} Shutdown
                        </button>
                        <span class="action-separator">|</span>
                    ` : ''}
                    ${editMode ? `
                        <button class="device-action" onclick="App.editDevice(${index})">
                            ${this.icons.getIcon('pencil')} Edit
                        </button>
                        <button class="device-action danger" onclick="App.deleteDevice(${index})">
                            ${this.icons.getIcon('trash-2')} Delete
                        </button>
                    ` : ''}
                </div>
                
                ${containersHtml}
            </div>
        `;
    },

    /**
     * Render container row
     */
    renderContainerRow(deviceId, container) {
        const isRunning = container.status === 'running';
        const statusColor = isRunning ? 'var(--accent)' : 'var(--danger)';
        
        return `
            <div class="container-row">
                <span class="container-name">${this.escapeHtml(container.name)}</span>
                <div class="container-actions">
                    <span style="color: ${statusColor}; font-size: 10px">${container.status}</span>
                    ${isRunning ? `
                        <button class="device-action" onclick="App.dockerAction('${deviceId}', '${container.name}', 'stop')" title="Stop">
                            ${this.icons.getIcon('square')}
                        </button>
                        <button class="device-action" onclick="App.dockerAction('${deviceId}', '${container.name}', 'restart')" title="Restart">
                            ${this.icons.getIcon('rotate-cw')}
                        </button>
                    ` : `
                        <button class="device-action" onclick="App.dockerAction('${deviceId}', '${container.name}', 'start')" title="Start">
                            ${this.icons.getIcon('play')}
                        </button>
                    `}
                    <div class="container-spinner" id="spinner-${deviceId}-${container.name}"></div>
                </div>
            </div>
        `;
    },

    // ===== TASKS =====

    /**
     * Render tasks list
     * @param {Array} tasks
     * @param {object} runningTasks
     * @param {boolean} editMode
     */
    renderTasks(tasks, runningTasks = {}, editMode = false) {
        const list = document.getElementById('tasks-list');
        if (!list) return;

        if (!tasks || tasks.length === 0) {
            list.innerHTML = '<div class="task-empty">No scheduled tasks</div>';
            return;
        }

        list.innerHTML = tasks.map((task, index) => {
            const isRunning = runningTasks[task.id];
            const isEnabled = task.enabled !== false;
            
            return `
                <div class="task-card">
                    <div class="task-header">
                        <div class="task-icon">${this.icons.getIcon(this.getTaskIcon(task.type))}</div>
                        <div class="task-info">
                            <div class="task-name">${this.escapeHtml(task.name)}</div>
                            <div class="task-schedule">${this.formatSchedule(task)}</div>
                            ${task.next_run ? `<div class="task-next">Next: ${this.formatDate(task.next_run)}</div>` : ''}
                        </div>
                        <div class="task-status ${isRunning ? 'running' : ''} ${!isEnabled ? 'disabled' : ''}">
                            ${isRunning ? 'Running' : (isEnabled ? 'Active' : 'Disabled')}
                        </div>
                    </div>
                    <div class="task-actions">
                        <button class="task-btn" onclick="App.runTask('${task.id}')" ${isRunning ? 'disabled' : ''}>
                            ${this.icons.getIcon('play')} Run Now
                        </button>
                        <button class="task-btn" onclick="App.toggleTask('${task.id}')">
                            ${this.icons.getIcon(isEnabled ? 'pause' : 'play')} ${isEnabled ? 'Disable' : 'Enable'}
                        </button>
                        ${editMode ? `
                            <button class="task-btn" onclick="App.editTask(${index})">
                                ${this.icons.getIcon('pencil')} Edit
                            </button>
                            <button class="task-btn danger" onclick="App.deleteTask(${index})">
                                ${this.icons.getIcon('trash-2')} Delete
                            </button>
                        ` : ''}
                    </div>
                </div>
            `;
        }).join('');

        // Re-initialize Lucide icons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    },

    /**
     * Get task icon based on type
     */
    getTaskIcon(type) {
        const icons = {
            'docker': 'box',
            'command': 'terminal',
            'http': 'globe',
            'backup': 'hard-drive'
        };
        return icons[type] || 'clock';
    },

    /**
     * Format task schedule for display
     */
    formatSchedule(task) {
        if (task.schedule === 'interval') {
            return `Every ${task.interval_value} ${task.interval_unit}`;
        }
        if (task.schedule === 'daily') {
            return `Daily at ${task.time || '00:00'}`;
        }
        if (task.schedule === 'weekly') {
            const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
            const dayNames = (task.days || []).map(d => days[d]).join(', ');
            return `${dayNames} at ${task.time || '00:00'}`;
        }
        if (task.schedule === 'cron') {
            return `Cron: ${task.cron}`;
        }
        return task.schedule || 'Manual';
    },

    // ===== MODALS =====

    /**
     * Show modal
     * @param {string} id - Modal element ID
     */
    showModal(id) {
        const modal = document.getElementById(id);
        if (modal) {
            modal.classList.add('visible');
        }
    },

    /**
     * Hide modal
     * @param {string} id - Modal element ID
     */
    hideModal(id) {
        const modal = document.getElementById(id);
        if (modal) {
            modal.classList.remove('visible');
        }
    },

    /**
     * Hide all modals
     */
    hideAllModals() {
        document.querySelectorAll('.modal.visible').forEach(modal => {
            modal.classList.remove('visible');
        });
    },

    // ===== THEME =====

    /**
     * Apply theme settings
     * @param {object} settings
     */
    applyTheme(settings) {
        if (!settings) return;

        const root = document.documentElement;
        
        if (settings.bg_primary) root.style.setProperty('--bg-primary', settings.bg_primary);
        if (settings.bg_secondary) root.style.setProperty('--bg-secondary', settings.bg_secondary);
        if (settings.border) root.style.setProperty('--border', settings.border);
        if (settings.text_color) root.style.setProperty('--text-primary', settings.text_color);
        if (settings.text_muted) root.style.setProperty('--text-secondary', settings.text_muted);
        if (settings.accent_color) root.style.setProperty('--accent', settings.accent_color);
        
        // Glass effect
        if (settings.glass !== undefined) {
            const opacity = 1 - (settings.glass / 100);
            root.style.setProperty('--glass-opacity', opacity);
        }
        if (settings.blur !== undefined) {
            root.style.setProperty('--glass-blur', settings.blur + 'px');
        }

        // Wallpaper
        if (settings.wallpaper) {
            document.body.style.backgroundImage = `url(${settings.wallpaper})`;
            document.body.style.backgroundSize = 'cover';
            document.body.style.backgroundPosition = 'center';
            document.body.style.backgroundAttachment = 'fixed';
        } else {
            document.body.style.backgroundImage = '';
        }
    },

    /**
     * Load theme inputs with current values
     */
    loadThemeInputs(settings) {
        if (!settings) return;

        const inputs = {
            'theme-bg': settings.bg_primary,
            'theme-cards': settings.bg_secondary,
            'theme-border': settings.border,
            'theme-text': settings.text_color,
            'theme-text-muted': settings.text_muted,
            'theme-accent': settings.accent_color,
            'theme-glass': settings.glass || 0,
            'theme-blur': settings.blur || 0,
            'theme-wallpaper': settings.wallpaper || ''
        };

        for (const [id, value] of Object.entries(inputs)) {
            const el = document.getElementById(id);
            if (el) {
                el.value = value;
                // Also update hex inputs
                const hexEl = document.getElementById(id + '-hex');
                if (hexEl) hexEl.value = value;
            }
        }

        // Update slider labels
        const glassLabel = document.getElementById('theme-glass-value');
        if (glassLabel) glassLabel.textContent = (settings.glass || 0) + '%';
        
        const blurLabel = document.getElementById('theme-blur-value');
        if (blurLabel) blurLabel.textContent = (settings.blur || 0) + 'px';
    },

    // ===== SECTION VISIBILITY =====

    /**
     * Update section visibility based on hidden state
     * @param {object} hiddenSections
     */
    updateSectionVisibility(hiddenSections = {}) {
        ['links', 'devices', 'tasks'].forEach(section => {
            const el = document.getElementById(`${section}-section`);
            if (el) {
                if (hiddenSections[section]) {
                    el.classList.add('section-hidden');
                } else {
                    el.classList.remove('section-hidden');
                }
            }
        });
    },

    // ===== FILE MANAGER =====

    /**
     * Render file list in pane
     * @param {string} paneId - 'left' or 'right'
     * @param {Array} files
     * @param {string} currentPath
     */
    renderFileList(paneId, files, currentPath) {
        const list = document.getElementById(`fm-list-${paneId}`);
        const pathEl = document.getElementById(`fm-path-${paneId}`);
        
        if (pathEl) pathEl.textContent = currentPath;
        if (!list) return;

        // Add parent directory entry
        let html = '';
        if (currentPath !== '/' && currentPath !== '') {
            html += `
                <div class="fm-item" data-path=".." data-type="dir">
                    <div class="fm-icon">${this.icons.getIcon('folder-up')}</div>
                    <span class="fm-name">..</span>
                </div>
            `;
        }

        html += files.map(file => {
            const icon = file.is_dir ? 'folder' : this.getFileIcon(file.name);
            const size = file.is_dir ? '' : this.formatSize(file.size);
            
            return `
                <div class="fm-item" data-path="${this.escapeHtml(file.name)}" data-type="${file.is_dir ? 'dir' : 'file'}">
                    <div class="fm-icon">${this.icons.getIcon(icon)}</div>
                    <span class="fm-name">${this.escapeHtml(file.name)}</span>
                    <span class="fm-size">${size}</span>
                    <span class="fm-date">${file.modified ? this.formatDate(file.modified) : ''}</span>
                </div>
            `;
        }).join('');

        list.innerHTML = html;

        // Re-initialize Lucide icons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    },

    /**
     * Get file icon based on extension
     */
    getFileIcon(filename) {
        const ext = filename.split('.').pop().toLowerCase();
        const icons = {
            'js': 'file-code',
            'ts': 'file-code',
            'py': 'file-code',
            'html': 'file-code',
            'css': 'file-code',
            'json': 'file-json',
            'md': 'file-text',
            'txt': 'file-text',
            'pdf': 'file-text',
            'jpg': 'image',
            'jpeg': 'image',
            'png': 'image',
            'gif': 'image',
            'svg': 'image',
            'mp3': 'music',
            'mp4': 'video',
            'zip': 'file-archive',
            'tar': 'file-archive',
            'gz': 'file-archive'
        };
        return icons[ext] || 'file';
    },

    // ===== UTILITY FUNCTIONS =====

    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    },

    /**
     * Format file size
     */
    formatSize(bytes) {
        if (!bytes) return '';
        const units = ['B', 'KB', 'MB', 'GB', 'TB'];
        let i = 0;
        while (bytes >= 1024 && i < units.length - 1) {
            bytes /= 1024;
            i++;
        }
        return bytes.toFixed(i > 0 ? 1 : 0) + ' ' + units[i];
    },

    /**
     * Format date
     */
    formatDate(date) {
        if (!date) return '';
        const d = new Date(date);
        if (isNaN(d.getTime())) return date;
        return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    },

    /**
     * Generate unique ID
     */
    generateId() {
        return 'id_' + Math.random().toString(36).substr(2, 9);
    }
};

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = UI;
}
