/**
 * @file main.js
 * @description Script principal para toda la funcionalidad interactiva de la aplicación Hepta-Conexiones.
 * @author Yimmy Moreno (con asistencia de IA)
 * @version 3.2.0
 */

// El evento 'DOMContentLoaded' asegura que el script se ejecute solo después de que
// todo el contenido HTML de la página haya sido cargado y parseado por el navegador.
// Este es el punto de entrada principal de nuestro JavaScript.
(function() {
    document.addEventListener('DOMContentLoaded', function () {
        initializeApp();
    });
})();

/**
 * @function initializeApp
 * @description Función principal que orquesta la inicialización de todos los componentes y funcionalidades de la UI.
 */
function initializeApp() {
    // Se inicializan los componentes globales que pueden estar en cualquier página.
    initTooltips();
    initThemeToggle();
    initSidebar();
    initNotifications();
    initDeleteModals(); // Lógica para los modales de confirmación.

    // Se inicializan los componentes específicos del Dashboard
    initDashboardCustomization(); // NUEVO: Personalización del dashboard
    initQuickActions(); // NUEVO: Acciones rápidas en tareas
    initTaskFilters(); // NUEVO: Filtros de tareas en dashboard

    // Se inicializan los componentes específicos que solo existen en ciertas páginas.
    if (document.getElementById('catalogo-container')) {
        initCatalogo();
    }
    if (document.getElementById('admin-dashboard-charts')) {
        initDashboardCharts(); // Asume que Chart.js ya está disponible
    }
    if (document.getElementById('myProjectsChart')) {
        initMyProjectsChart(); // NUEVO: Gráfico de resumen de proyectos del usuario
    }
    if (document.getElementById('myPerformanceChart')) {
        initMyPerformanceChart(); // NUEVO: Gráfico de rendimiento del usuario
    }
    if (document.getElementById('tiempoPorEstadoChart')) {
        initEficienciaCharts(); // Asume que Chart.js ya está disponible
    }
    // NUEVO: Inicializar autocompletado si estamos en formularios de conexión
    if (document.querySelector('input[name^="perfil_"]')) {
        initProfileAutocomplete();
    }
}

/**
 * @function initTooltips
 * @description Inicializa los tooltips de Bootstrap en toda la aplicación.
 */
function initTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

/**
 * @function initThemeToggle
 * @description Gestiona la funcionalidad del interruptor de tema (claro/oscuro).
 */
function initThemeToggle() {
    const themeToggle = document.getElementById('theme-toggle');
    if (!themeToggle) return;

    const currentTheme = document.documentElement.getAttribute('data-bs-theme');
    if (currentTheme === 'light') {
        themeToggle.checked = true;
    }

    themeToggle.addEventListener('change', function () {
        const theme = this.checked ? 'light' : 'dark';
        document.documentElement.setAttribute('data-bs-theme', theme);
        
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
        if (csrfToken) {
            fetch('/api/set-theme', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ theme: theme })
            }).catch(error => console.error('Error al guardar la preferencia de tema:', error));
        }
    });
}

/**
 * @function initSidebar
 * @description Gestiona la funcionalidad de la barra lateral (sidebar).
 */
function initSidebar() {
    const hamburgerBtn = document.getElementById('hamburger-btn');
    const sidebar = document.getElementById('sidebar');
    const sidebarOverlay = document.getElementById('sidebar-overlay');
    const sidebarCloseBtn = document.getElementById('sidebar-close-btn');

    if (!hamburgerBtn || !sidebar || !sidebarOverlay || !sidebarCloseBtn) return;

    const openSidebar = () => {
        sidebar.classList.add('active');
        sidebarOverlay.classList.add('active');
    };
    const closeSidebar = () => {
        sidebar.classList.remove('active');
        sidebarOverlay.classList.remove('active');
    };

    hamburgerBtn.addEventListener('click', openSidebar);
    sidebarOverlay.addEventListener('click', closeSidebar);
    sidebarCloseBtn.addEventListener('click', closeSidebar);
}

/**
 * @function initNotifications
 * @description Gestiona el sistema de notificaciones.
 */
function initNotifications() {
    const notificationBell = document.getElementById('notification-bell');
    if (!notificationBell) return;

    notificationBell.addEventListener('click', function() {
        const badge = this.querySelector('.notification-badge');
        if (badge) {
            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
            if (!csrfToken) {
                console.error("Token CSRF no encontrado para marcar notificaciones.");
                return;
            }
            fetch('/api/notificaciones/marcar-leidas', {
                method: 'POST',
                 headers: { 'X-CSRFToken': csrfToken }
            }).then(response => {
                if (response.ok) return response.json();
                throw new Error('La respuesta de la red no fue exitosa.');
            }).then(data => {
                  if(data.success) {
                      badge.remove();
                  }
              }).catch(error => console.error('Error al marcar notificaciones como leídas:', error));
        }
    });
}

/**
 * @function initDeleteModals
 * @description Centraliza la lógica para todos los modales de confirmación.
 */
function initDeleteModals() {
    const confirmDeleteModal = document.getElementById('confirmDeleteModal');
    if (confirmDeleteModal) {
        confirmDeleteModal.addEventListener('show.bs.modal', function (event) {
            const button = event.relatedTarget;
            const formAction = button.getAttribute('data-form-action');
            const itemName = button.getAttribute('data-item-name');
            
            const modalBodyStrong = confirmDeleteModal.querySelector('#itemName');
            const deleteForm = confirmDeleteModal.querySelector('#deleteForm');
            
            if (modalBodyStrong) modalBodyStrong.textContent = itemName;
            if (deleteForm) deleteForm.action = formAction;
        });
    }

    const confirmToggleModal = document.getElementById('confirmToggleModal');
    if (confirmToggleModal) {
        confirmToggleModal.addEventListener('show.bs.modal', function (event) {
            const button = event.relatedTarget;
            const formAction = button.getAttribute('data-form-action');
            const userName = button.getAttribute('data-user-name');
            const actionText = button.getAttribute('data-action-text');
            
            confirmToggleModal.querySelector('#actionText').textContent = actionText.toLowerCase();
            confirmToggleModal.querySelector('#userName').textContent = userName;
            confirmToggleModal.querySelector('#toggleForm').action = formAction;
            confirmToggleModal.querySelector('#confirmToggleButton').textContent = `Sí, ${actionText}`;
        });
    }

    // Lógica para el modal de rechazo (si existe en la página, se usa en detalle_conexion y dashboard)
    const rejectModal = document.getElementById('rejectModal');
    if (rejectModal) {
        rejectModal.addEventListener('show.bs.modal', function (event) {
            const button = event.relatedTarget; // Botón que activa el modal
            const conexionId = button.getAttribute('data-conexion-id');
            const form = rejectModal.querySelector('form');
            if (form && conexionId) {
                // Actualiza la URL de acción si el formulario es de POST directo (no AJAX)
                // Si usas AJAX, esta parte se gestiona en initQuickActions
                form.action = `/conexiones/${conexionId}/cambiar_estado`;
            }
        });
    }
}

/**
 * @function initCatalogo
 * @description Inicializa toda la lógica interactiva de la página del Catálogo de Conexiones.
 */
function initCatalogo() {
    const catalogoContainer = document.getElementById('catalogo-container');
    const proyectoSelect = document.getElementById('proyecto-select');
    const searchInput = document.getElementById('search-input');
    const tipologiasWrapper = document.getElementById('tipologias-wrapper');
    const tipologiaLinks = document.querySelectorAll('.tipologia-link');
    const noResultsDiv = document.getElementById('no-results');
    const baseUrl = catalogoContainer.dataset.baseUrl;

    function updateCatalogoState() {
        const proyectoId = proyectoSelect.value;
        const isDisabled = !proyectoId;
        
        tipologiasWrapper.classList.toggle('disabled-section', isDisabled);
        searchInput.disabled = isDisabled;
        tipologiaLinks.forEach(link => link.classList.toggle('disabled', isDisabled));
        if (isDisabled) {
            searchInput.value = '';
            filterTipologias();
        }
    }

    function filterTipologias() {
        const searchTerm = searchInput.value.toLowerCase().trim();
        let visibleCount = 0;

        document.querySelectorAll('.accordion-item').forEach(accordionItem => {
            let accordionVisibleLinks = 0;
            accordionItem.querySelectorAll('.tipologia-link').forEach(link => {
                const name = link.querySelector('.tipologia-name').textContent.toLowerCase();
                const isVisible = name.includes(searchTerm);
                link.style.display = isVisible ? 'flex' : 'none';
                if(isVisible) {
                    visibleCount++;
                    accordionVisibleLinks++;
                }
            });
            accordionItem.style.display = accordionVisibleLinks > 0 ? 'block' : 'none';
        });

        noResultsDiv.style.display = (visibleCount === 0 && searchTerm.length > 0) ? 'block' : 'none';
    }

    searchInput.addEventListener('input', filterTipologias);
    
    tipologiaLinks.forEach(link => {
        link.addEventListener('click', function(event) {
            event.preventDefault();
            if (this.classList.contains('disabled')) return;
            
            const proyectoId = proyectoSelect.value;
            if (!proyectoId) {
                alert("Por favor, selecciona un proyecto primero.");
                return;
            }

            const tipo = this.dataset.tipo;
            const subtipo = this.dataset.subtipo;
            const tipologia = this.dataset.tipologia;
            
            const url = new URL(window.location.origin + baseUrl);
            url.searchParams.append('proyecto_id', proyectoId);
            url.searchParams.append('tipo', tipo);
            url.searchParams.append('subtipo', subtipo);
            url.searchParams.append('tipologia', tipologia);
            
            window.location.href = url.href;
        });
    });
    
    updateCatalogoState();
    proyectoSelect.addEventListener('change', updateCatalogoState);
}

/**
 * @function initDashboardCharts
 * @description Orquesta la inicialización de todos los gráficos en el Dashboard (para Administradores).
 */
function initDashboardCharts() {
    const dataEl = document.getElementById('dashboard-data');
    if (!dataEl) return;
    
    const estadosData = JSON.parse(dataEl.dataset.estados);
    const mesesData = JSON.parse(dataEl.dataset.meses);

    const ctx1 = document.getElementById('estadosChart');
    if (ctx1) {
        if (Object.keys(estadosData).length === 0) {
            ctx1.parentElement.innerHTML = '<div class="empty-state text-center p-5"><i class="bi bi-pie-chart" style="font-size: 2rem;"></i><p class="text-muted mt-2">No hay datos para mostrar el gráfico.</p></div>';
        } else {
            const stateColorMap = {
                'SOLICITADO': 'rgba(13, 110, 253, 0.7)',
                'EN_PROCESO': 'rgba(13, 202, 240, 0.7)',
                'REALIZADO': 'rgba(255, 193, 7, 0.7)',
                'APROBADO': 'rgba(25, 135, 84, 0.7)',
                'RECHAZADO': 'rgba(220, 53, 69, 0.7)'
            };
            const labels = Object.keys(estadosData);
            new Chart(ctx1, {
                type: 'doughnut',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Conexiones',
                        data: Object.values(estadosData),
                        backgroundColor: labels.map(label => stateColorMap[label] || '#6c757d'),
                        borderColor: '#343a40',
                        hoverOffset: 4
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'top' } } }
            });
        }
    }

    const ctx2 = document.getElementById('mesesChart');
    if (ctx2 && typeof mesesData !== 'undefined') {
        if (mesesData.length === 0) {
            ctx2.parentElement.innerHTML = '<div class="empty-state text-center p-5"><i class="bi bi-bar-chart-line" style="font-size: 2rem;"></i><p class="text-muted mt-2">No hay datos para mostrar el gráfico.</p></div>';
        } else {
            new Chart(ctx2, {
                type: 'bar',
                data: {
                    labels: mesesData.map(row => row.mes),
                    datasets: [{
                        label: 'Conexiones creadas',
                        data: mesesData.map(row => row.total),
                        backgroundColor: 'rgba(13, 110, 253, 0.5)',
                        borderColor: 'rgba(13, 110, 253, 1)',
                        borderWidth: 1
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } }, plugins: { legend: { display: false } } }
            });
        }
    }
}

/**
 * @function initMyProjectsChart
 * @description Inicializa el gráfico de resumen de proyectos para el usuario.
 */
function initMyProjectsChart() {
    const dataEl = document.getElementById('dashboard-data');
    if (!dataEl) return;
    const myProjectsSummary = JSON.parse(dataEl.dataset.projectsSummary);

    const ctx = document.getElementById('myProjectsChart');
    if (!ctx) return;

    if (myProjectsSummary.length === 0) {
        ctx.parentElement.innerHTML = '<div class="empty-state text-center p-5"><i class="bi bi-bar-chart-steps" style="font-size: 2rem;"></i><p class="text-muted mt-2">No tienes proyectos para mostrar en el gráfico.</p></div>';
        return;
    }

    const labels = myProjectsSummary.map(p => p.nombre);
    
    const stateColorMap = {
        solicitadas: 'rgba(13, 110, 253, 0.7)',
        en_proceso: 'rgba(13, 202, 240, 0.7)',
        aprobadas: 'rgba(25, 135, 84, 0.7)',
        rechazadas: 'rgba(220, 53, 69, 0.7)'
    };

    const datasets = [
        {
            label: 'Solicitadas',
            data: myProjectsSummary.map(p => p.solicitadas),
            backgroundColor: stateColorMap.solicitadas,
        },
        {
            label: 'En Proceso',
            data: myProjectsSummary.map(p => p.en_proceso),
            backgroundColor: stateColorMap.en_proceso,
        },
        {
            label: 'Aprobadas',
            data: myProjectsSummary.map(p => p.aprobadas),
            backgroundColor: stateColorMap.aprobadas,
        },
        {
            label: 'Rechazadas',
            data: myProjectsSummary.map(p => p.rechazadas),
            backgroundColor: stateColorMap.rechazadas,
        }
    ];

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            onClick: (event, elements, chart) => {
                if (elements.length === 0) return; // No se hizo clic en una barra

                const firstElement = elements[0];
                const datasetIndex = firstElement.datasetIndex;
                const index = firstElement.index;

                const projectName = chart.data.labels[index];
                const statusLabel = chart.data.datasets[datasetIndex].label;

                // Encontrar el ID del proyecto
                const project = myProjectsSummary.find(p => p.nombre === projectName);
                if (!project) return;
                const projectId = project.id;
                
                // Mapear la etiqueta del gráfico al estado de la base de datos
                const statusMap = {
                    'Solicitadas': 'SOLICITADO',
                    'En Proceso': 'EN_PROCESO',
                    'Aprobadas': 'APROBADO',
                    'Rechazadas': 'RECHAZADO'
                };
                const status = statusMap[statusLabel];
                if (!status) return;

                // Mostrar el modal y cargar los datos
                const modalEl = document.getElementById('chartDrilldownModal');
                const modal = new bootstrap.Modal(modalEl);
                const modalTitle = modalEl.querySelector('.modal-title');
                const modalBody = modalEl.querySelector('#drilldown-table-body');
                
                modalTitle.textContent = `Conexiones en estado "${statusLabel}" para ${projectName}`;
                modalBody.innerHTML = '<tr><td colspan="3" class="text-center">Cargando...</td></tr>';
                modal.show();

                fetch(`/api/dashboard/project-details?proyecto_id=${projectId}&estado=${status}`)
                    .then(response => {
                        if (!response.ok) throw new Error('Error al cargar los datos.');
                        return response.json();
                    })
                    .then(data => {
                        modalBody.innerHTML = ''; // Limpiar el "Cargando..."
                        if (data.length === 0) {
                            modalBody.innerHTML = '<tr><td colspan="3" class="text-center">No se encontraron conexiones.</td></tr>';
                        } else {
                            data.forEach(conn => {
                                const tr = document.createElement('tr');

                                // Celda para el código de conexión (usando textContent para seguridad XSS)
                                const tdCode = document.createElement('td');
                                const strong = document.createElement('strong');
                                strong.textContent = conn.codigo_conexion;
                                tdCode.appendChild(strong);
                                tr.appendChild(tdCode);

                                // Celda para la fecha
                                const tdDate = document.createElement('td');
                                tdDate.textContent = new Date(conn.fecha_creacion).toLocaleString();
                                tr.appendChild(tdDate);

                                // Celda para el botón de acción
                                const tdAction = document.createElement('td');
                                const actionLink = document.createElement('a');
                                actionLink.href = `/conexiones/${conn.id}`;
                                actionLink.className = 'btn btn-sm btn-secondary';
                                actionLink.textContent = 'Ver';
                                tdAction.appendChild(actionLink);
                                tr.appendChild(tdAction);

                                modalBody.appendChild(tr);
                            });
                        }
                    })
                    .catch(error => {
                        console.error('Error en drill-down:', error);
                        modalBody.innerHTML = `<tr><td colspan="3" class="text-center text-danger">${error.message}</td></tr>`;
                    });
            },
            plugins: {
                title: {
                    display: true,
                    text: 'Estado de Conexiones por Proyecto'
                },
                tooltip: {
                    mode: 'index',
                    intersect: false
                }
            },
            scales: {
                x: {
                    stacked: true,
                },
                y: {
                    stacked: true,
                    beginAtZero: true,
                    ticks: {
                        stepSize: 1
                    }
                }
            }
        }
    });
}

/**
 * @function initMyPerformanceChart
 * @description Inicializa el gráfico de rendimiento del usuario.
 */
function initMyPerformanceChart() {
    const dataEl = document.getElementById('dashboard-data');
    if (!dataEl) return;
    const myPerformanceChartData = JSON.parse(dataEl.dataset.performanceChart);

    const ctx = document.getElementById('myPerformanceChart');
    if (!ctx) return;

    if (!myPerformanceChartData.labels || myPerformanceChartData.labels.length === 0) {
        ctx.parentElement.innerHTML = '<div class="empty-state text-center p-4"><i class="bi bi-graph-up" style="font-size: 2rem;"></i><p class="text-muted mt-2">No hay datos de rendimiento para mostrar.</p></div>';
        return;
    }

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: myPerformanceChartData.labels,
            datasets: [{
                label: 'Tareas Completadas',
                data: myPerformanceChartData.data,
                fill: true,
                borderColor: 'rgba(25, 135, 84, 1)',
                backgroundColor: 'rgba(25, 135, 84, 0.2)',
                tension: 0.1,
                pointBackgroundColor: 'rgba(25, 135, 84, 1)'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        stepSize: 1
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                }
            }
        }
    });
}


/**
 * @function initEficienciaCharts
 * @description Inicializa los gráficos de la página de Análisis de Eficiencia.
 */
function initEficienciaCharts() {
    const ctx1 = document.getElementById('tiempoPorEstadoChart');
    if (ctx1 && typeof timeByStateData !== 'undefined') {
        new Chart(ctx1, {
            type: 'bar',
            data: {
                labels: Object.keys(timeByStateData),
                datasets: [{
                    label: 'Horas Promedio',
                    data: Object.values(timeByStateData),
                    backgroundColor: ['rgba(255, 159, 64, 0.5)', 'rgba(54, 162, 235, 0.5)', 'rgba(75, 192, 192, 0.5)'],
                    borderColor: ['rgba(255, 159, 64, 1)', 'rgba(54, 162, 235, 1)', 'rgba(75, 192, 192, 1)'],
                    borderWidth: 1
                }]
            },
            options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
        });
    }

    const ctx2 = document.getElementById('conexionesPorRealizadorChart');
    if (ctx2 && typeof completedByUserData !== 'undefined') {
        new Chart(ctx2, {
            type: 'bar',
            data: {
                labels: completedByUserData.map(row => row.user),
                datasets: [{
                    label: 'Conexiones Completadas',
                    data: completedByUserData.map(row => row.total),
                    backgroundColor: 'rgba(111, 66, 193, 0.5)',
                    borderColor: 'rgba(111, 66, 193, 1)',
                    borderWidth: 1
                }]
            },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
        });
    }
}

/**
 * @function initProfileAutocomplete
 * @description Inicializa la funcionalidad de autocompletado para los campos de perfil.
 */
function initProfileAutocomplete() {
    const profileInputs = document.querySelectorAll('input[name^="perfil_"]');
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');

    if (!profileInputs.length || !csrfToken) return;

    profileInputs.forEach(input => {
        let datalist = document.createElement('datalist');
        datalist.id = input.id + '-suggestions';
        input.setAttribute('list', datalist.id);
        input.after(datalist);

        let currentAbortController = null;

        input.addEventListener('input', function() {
            const query = this.value.trim();
            if (query.length < 2) {
                datalist.innerHTML = '';
                return;
            }

            if (currentAbortController) {
                currentAbortController.abort();
            }
            currentAbortController = new AbortController();
            const signal = currentAbortController.signal;

            fetch(`/api/perfiles/buscar?q=${encodeURIComponent(query)}`, {
                headers: { 'X-CSRFToken': csrfToken },
                signal: signal
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                datalist.innerHTML = '';
                if (data.length > 0) {
                    data.forEach(item => {
                        let option = document.createElement('option');
                        option.value = item.value;
                        option.textContent = item.label;
                        datalist.appendChild(option);
                    });
                }
            })
            .catch(error => {
                if (error.name === 'AbortError') {
                    console.log('Fetch aborted:', query);
                } else {
                    console.error('Error fetching profile suggestions:', error);
                }
            });
        });

        input.addEventListener('blur', function() {
            setTimeout(() => {
                if (!this.value.trim()) {
                    datalist.innerHTML = '';
                }
            }, 100);
        });
    });
}


// NUEVA FUNCIÓN: Personalización del Dashboard
function initDashboardCustomization() {
    const customizeBtn = document.getElementById('customize-dashboard-btn');
    const customizeModalEl = document.getElementById('customizeDashboardModal');
    const dataEl = document.getElementById('dashboard-data');

    if (!customizeModalEl || !dataEl) return;

    const userPreferences = JSON.parse(dataEl.dataset.userPrefs);
    const customizeModal = new bootstrap.Modal(customizeModalEl);
    const savePreferencesBtn = document.getElementById('saveDashboardPreferences');
    const toggleWidgets = customizeModalEl.querySelectorAll('[data-widget-id]');

    function applyPreferences(prefs) {
        const widgetsConfig = prefs.widgets_config || {};
        const defaultVisibleWidgets = {
            'my-summary-panel': true, 'my-performance-panel': true,
            'my-projects-summary-panel': true, 'quick-actions-panel': true,
            'tasks-panel': true, 'recent-activity-panel': true, 'admin-panel': true
        };

        document.querySelectorAll('[id$="-panel"]').forEach(panel => {
            const panelId = panel.id;
            const isVisible = widgetsConfig.hasOwnProperty(panelId) ? widgetsConfig[panelId] : defaultVisibleWidgets[panelId];
            panel.style.display = isVisible ? '' : 'none';
            const toggle = customizeModalEl.querySelector(`[data-widget-id="${panelId}"]`);
            if (toggle) toggle.checked = isVisible;
        });
    }

    applyPreferences(userPreferences);

    if (customizeBtn) {
        customizeBtn.addEventListener('click', () => {
            customizeModal.show();
        });
    }

    if (savePreferencesBtn) {
        savePreferencesBtn.addEventListener('click', () => {
            const newWidgetsConfig = {};
            toggleWidgets.forEach(toggle => {
                const widgetId = toggle.dataset.widgetId;
                newWidgetsConfig[widgetId] = toggle.checked;
            });

            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
            if (!csrfToken) { console.error("CSRF token not found."); return; }

            fetch('/api/dashboard/save_preferences', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ widgets_config: newWidgetsConfig })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    console.log('Preferencias guardadas:', data.message);
                    // Aplicar los cambios inmediatamente a la vista
                    applyPreferences({ widgets_config: newWidgetsConfig });
                    customizeModal.hide();
                    // Opcional: mostrar un SweetAlert de éxito
                } else {
                    console.error('Error al guardar preferencias:', data.message);
                    alert('Error al guardar preferencias: ' + data.message); // Fallback a alert
                }
            })
            .catch(error => {
                console.error('Error de red al guardar preferencias:', error);
                alert('Ocurrió un error de red al guardar preferencias.'); // Fallback a alert
            });
        });
    }
}

// NUEVA FUNCIÓN: Acciones Rápidas (Tomar, Realizado, Aprobar, Rechazar)
function initQuickActions() {
    document.addEventListener('click', function(event) {
        // Asegúrate de que el clic es en un botón de acción rápida
        if (event.target.classList.contains('quick-action-btn')) {
            const button = event.target;
            const conexionId = button.dataset.id;
            const estado = button.dataset.estado;
            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');

            if (!csrfToken) { console.error("CSRF token not found."); return; }

            let data = { estado: estado };
            if (estado === 'RECHAZADO') {
                const rejectModalEl = document.getElementById('rejectModal');
                const rejectModal = new bootstrap.Modal(rejectModalEl);
                
                // Limpiar el campo de texto y asegurar que el ID de conexión se pasa al modal
                rejectModalEl.querySelector('#rejectDetails').value = '';
                rejectModalEl.dataset.conexionId = conexionId; 
                
                rejectModal.show();

                // Usamos un listener para el botón de envío del modal de rechazo
                // para evitar múltiples listeners si se hace clic varias veces en "Rechazar"
                const rejectSubmitBtn = rejectModalEl.querySelector('.btn-danger[type="submit"]');
                // Clonar y reemplazar el botón para eliminar listeners anteriores
                const newRejectSubmitBtn = rejectSubmitBtn.cloneNode(true);
                rejectSubmitBtn.parentNode.replaceChild(newRejectSubmitBtn, rejectSubmitBtn);

                newRejectSubmitBtn.addEventListener('click', function submitReject() {
                    const motive = rejectModalEl.querySelector('#rejectDetails').value;
                    if (!motive) {
                        alert("Debes proporcionar un motivo para el rechazo.");
                        return;
                    }
                    data.detalles = motive;
                    sendQuickAction(rejectModalEl.dataset.conexionId, data, csrfToken);
                    rejectModal.hide();
                    newRejectSubmitBtn.removeEventListener('click', submitReject); // Limpiar listener
                });
                return; // Detener el flujo para que el modal maneje el envío
            }

            // Para otras acciones (Tomar, Realizado, Aprobar), enviar directamente
            sendQuickAction(conexionId, data, csrfToken);
        }
    });

    function sendQuickAction(conexionId, data, csrfToken) {
        // CORRECCIÓN: La URL apuntaba a un endpoint de API inexistente (/api/...).
        // Se corrige para usar el endpoint de cambio de estado estándar que ya existe
        // y funciona con datos de formulario (FormData).
        const formData = new FormData();
        for (const key in data) {
            formData.append(key, data[key]);
        }
        // Flask-WTF espera el token CSRF como un campo dentro del formulario.
        formData.append('csrf_token', csrfToken);

        fetch(`/conexiones/${conexionId}/cambiar_estado`, { // URL CORREGIDA
            method: 'POST',
            headers: {
                // Al usar FormData, no se debe establecer 'Content-Type' manualmente.
                // El navegador lo configura automáticamente con el 'boundary' correcto.
                // Mantenemos 'X-CSRFToken' por si algún middleware lo usa, aunque Flask-WTF lo busca en el cuerpo del form.
                'X-CSRFToken': csrfToken
            },
            body: formData // CUERPO CORREGIDO
        })
        .then(response => {
            if (!response.ok) {
                // Si la respuesta no es 2xx, leer el mensaje de error del backend
                return response.json().then(err => { throw new Error(err.message || 'Error desconocido del servidor'); });
            }
            return response.json();
        })
        .then(result => {
            if (result.success) {
                // SweetAlert2 para mensajes más amigables (asume que está cargado)
                if (typeof Swal !== 'undefined') {
                    Swal.fire({
                        icon: 'success',
                        title: '¡Éxito!',
                        text: result.message,
                        showConfirmButton: false,
                        timer: 1500
                    }).then(() => {
                        window.location.reload(); // Recargar el dashboard para ver los cambios
                    });
                } else {
                    alert(result.message);
                    window.location.reload();
                }
            } else {
                if (typeof Swal !== 'undefined') {
                    Swal.fire({
                        icon: 'error',
                        title: 'Error',
                        text: result.message
                    });
                } else {
                    alert(`Error: ${result.message}`);
                }
            }
        })
        .catch(error => {
            console.error('Error en la acción rápida:', error);
            if (typeof Swal !== 'undefined') {
                Swal.fire({
                    icon: 'error',
                    title: 'Error de Red',
                    text: 'Ocurrió un error al procesar la solicitud. Inténtalo de nuevo.'
                });
            } else {
                alert('Ocurrió un error al procesar la solicitud.');
            }
        });
    }
}

// NUEVA FUNCIÓN: Filtros de Tareas en Dashboard (filtrado en el lado del cliente)
function initTaskFilters() {
    const filterForm = document.getElementById('task-filters-form');
    if (!filterForm) return;

    const projectSelect = document.getElementById('task_filter_project');
    const typeSelect = document.getElementById('task_filter_type');
    const searchInput = document.getElementById('task_search_input');

    // Mapea los IDs de las pestañas a los selectores de los paneles de tareas
    const tabPanelSelectors = {
        'pendientes': '#pendientes .data-table tbody tr',
        'asignadas': '#asignadas .data-table tbody tr',
        'disponibles': '#disponibles .data-table tbody tr',
        'solicitudes': '#solicitudes .data-table tbody tr'
    };

    function applyTaskFilters() {
        const projectId = projectSelect.value;
        const type = typeSelect.value;
        const searchTerm = searchInput.value.toLowerCase().trim();

        // Itera sobre cada tipo de panel de tareas
        for (const tabId in tabPanelSelectors) {
            const rows = document.querySelectorAll(tabPanelSelectors[tabId]);
            rows.forEach(row => {
                const rowProjectId = row.dataset.projectId || ''; // Obtener de data-project-id
                const rowType = row.dataset.type ? row.dataset.type.toLowerCase() : ''; // Obtener de data-type
                const codeCell = row.querySelector('.task-code');
                const rowText = codeCell ? codeCell.textContent.toLowerCase() : '';

                const matchesProject = (projectId === '' || rowProjectId === projectId);
                const matchesType = (type === '' || rowType === type.toLowerCase());
                const matchesSearch = (searchTerm === '' || rowText.includes(searchTerm));
                
                row.style.display = (matchesProject && matchesType && matchesSearch) ? '' : 'none';
            });
        }
    }

    filterForm.addEventListener('change', applyTaskFilters);
    searchInput.addEventListener('input', applyTaskFilters);

    // Asegurarse de que los filtros se apliquen al cambiar de pestaña si ya hay valores
    const taskTabs = document.getElementById('taskTabs');
    if (taskTabs) {
        taskTabs.addEventListener('shown.bs.tab', applyTaskFilters);
    }
}