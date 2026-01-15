/**
 * Edge Analytics Dashboard - Main JavaScript
 * Handles refresh controls, chart interactions, and HTMX integration
 */

(function() {
    'use strict';
    
    // Dashboard State
    const Dashboard = {
        refreshInterval: 10, // seconds - default 10 seconds
        refreshTimer: null,
        countdownTimer: null,
        countdownSeconds: 10,
        isPaused: false,
        charts: {},
        
        init: function() {
            // Set default refresh interval to 10 seconds if not set
            if (!localStorage.getItem('dashboard-refresh-interval')) {
                localStorage.setItem('dashboard-refresh-interval', '10');
                this.refreshInterval = 10;
            } else {
                this.refreshInterval = parseInt(localStorage.getItem('dashboard-refresh-interval'), 10) || 10;
            }
            
            this.setupRefreshControls();
            this.setupMobileSidebar();
            this.setupHTMX();
            this.updateLastUpdated();
            
            // OPTIMIZATION: Immediately fetch collection metrics via AJAX on page load
            // This allows the page to render quickly while collection data loads in background
            console.log('⚡ Loading collection metrics in background...');
            setTimeout(() => {
                this.refreshData();
            }, 100); // Small delay to ensure page is fully rendered
        },
        
        /**
         * Setup refresh interval controls
         */
        setupRefreshControls: function() {
            const intervalSelect = document.getElementById('refresh-interval-select');
            const pauseBtn = document.getElementById('pause-refresh-btn');
            const intervalDisplay = document.getElementById('refresh-interval-display');
            
            // Set the select value and display
            if (intervalSelect) {
                intervalSelect.value = this.refreshInterval;
            }
            this.updateIntervalDisplay(intervalDisplay);
            
            // Handle interval change
            if (intervalSelect) {
                intervalSelect.addEventListener('change', (e) => {
                    this.refreshInterval = parseInt(e.target.value, 10);
                    localStorage.setItem('dashboard-refresh-interval', this.refreshInterval.toString());
                    this.updateIntervalDisplay(intervalDisplay);
                    this.startRefreshTimer();
                });
            }
            
            // Handle pause/resume
            if (pauseBtn) {
                pauseBtn.addEventListener('click', () => {
                    this.isPaused = !this.isPaused;
                    pauseBtn.textContent = this.isPaused ? 'Resume' : 'Pause';
                    
                    if (this.isPaused) {
                        this.stopRefreshTimer();
                    } else {
                        this.startRefreshTimer();
                    }
                    this.updateCountdownDisplay();
                });
            }
            
            // Start initial timer (auto-refresh every 10 seconds by default)
            if (this.refreshInterval > 0 && !this.isPaused) {
                this.startRefreshTimer();
            } else {
                // Still show countdown display even if paused or manual
                this.updateCountdownDisplay();
            }
        },
        
        /**
         * Update interval display text
         */
        updateIntervalDisplay: function(displayEl) {
            if (!displayEl) return;
            
            if (this.refreshInterval === 0) {
                displayEl.textContent = 'Manual';
            } else {
                displayEl.textContent = `${this.refreshInterval}s`;
            }
        },
        
        /**
         * Update countdown display
         */
        updateCountdownDisplay: function() {
            const countdownEl = document.getElementById('refresh-countdown');
            if (!countdownEl) return;
            
            if (this.isPaused || this.refreshInterval === 0) {
                countdownEl.textContent = this.refreshInterval === 0 ? 'Manual' : 'Paused';
            } else {
                // Display format: "10", "9", "8", "7" etc.
                countdownEl.textContent = `${this.countdownSeconds}`;
            }
        },
        
        /**
         * Start countdown timer
         */
        startCountdownTimer: function() {
            this.stopCountdownTimer();
            
            if (this.refreshInterval === 0 || this.isPaused) {
                this.updateCountdownDisplay();
                return;
            }
            
            // Reset countdown to refresh interval
            this.countdownSeconds = this.refreshInterval;
            this.updateCountdownDisplay();
            
            // Update countdown every second
            this.countdownTimer = setInterval(() => {
                if (this.isPaused || this.refreshInterval === 0) {
                    this.stopCountdownTimer();
                    this.updateCountdownDisplay();
                    return;
                }
                
                this.countdownSeconds--;
                this.updateCountdownDisplay();
                
                if (this.countdownSeconds <= 0) {
                    this.countdownSeconds = this.refreshInterval;
                }
            }, 1000);
        },
        
        /**
         * Stop countdown timer
         */
        stopCountdownTimer: function() {
            if (this.countdownTimer) {
                clearInterval(this.countdownTimer);
                this.countdownTimer = null;
            }
        },
        
        /**
         * Start refresh timer
         */
        startRefreshTimer: function() {
            this.stopRefreshTimer();
            
            if (this.refreshInterval === 0 || this.isPaused) {
                this.startCountdownTimer();
                return;
            }
            
            // Start countdown timer
            this.startCountdownTimer();
            
            // Start refresh timer - refresh every N seconds
            this.refreshTimer = setInterval(() => {
                if (!this.isPaused && this.refreshInterval > 0) {
                    console.log(`Auto-refresh triggered after ${this.refreshInterval} seconds`);
                    this.refreshData();
                }
            }, this.refreshInterval * 1000);
        },
        
        /**
         * Stop refresh timer
         */
        stopRefreshTimer: function() {
            if (this.refreshTimer) {
                clearInterval(this.refreshTimer);
                this.refreshTimer = null;
            }
            this.stopCountdownTimer();
        },
        
        /**
         * Refresh dashboard data via API call (no page reload)
         */
        refreshData: function() {
            console.log('Refreshing dashboard data via API...');
            
            // Get current URL parameters (filters)
            const urlParams = new URLSearchParams(window.location.search);
            const filters = {
                date_from: urlParams.get('date_from') || '',
                date_to: urlParams.get('date_to') || '',
                state: urlParams.getAll('state'),
                city: urlParams.getAll('city'),
                product: urlParams.get('product') || '',
                credit_person: urlParams.get('credit_person') || ''
            };
            
            // Build API URL with filters
            const apiUrl = new URL('/api/disbursal-data/', window.location.origin);
            Object.keys(filters).forEach(key => {
                if (filters[key]) {
                    if (Array.isArray(filters[key])) {
                        filters[key].forEach(val => {
                            if (val) apiUrl.searchParams.append(key, val);
                        });
                    } else if (filters[key]) {
                        apiUrl.searchParams.append(key, filters[key]);
                    }
                }
            });
            
            // Get token from localStorage
            const token = localStorage.getItem('blinkr_token');
            
            // Make API call
            fetch(apiUrl.toString(), {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest',
                    ...(token && { 'Authorization': `Bearer ${token}` })
                },
                credentials: 'same-origin'
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log('=== FULL API RESPONSE ===');
                console.log('Data refreshed successfully', data);
                console.log('All keys in response:', Object.keys(data));
                console.log('Collection Metrics in Response:', data.collection_metrics);
                console.log('Collection Metrics type:', typeof data.collection_metrics);
                console.log('Collection Metrics value:', JSON.stringify(data.collection_metrics));
                if (data.collection_metrics && Object.keys(data.collection_metrics).length > 0) {
                    console.log('Collection Metrics Keys:', Object.keys(data.collection_metrics));
                    console.log('Collection Metrics Full Object:', JSON.stringify(data.collection_metrics, null, 2));
                } else {
                    console.log('WARNING: collection_metrics is empty object {}');
                    console.log('This means the API call returned empty data or failed');
                }
                console.log('========================');
                this.updateDashboardData(data);
                this.updateLastUpdated();
            })
            .catch(error => {
                console.error('Error refreshing data:', error);
                // Fallback to page reload if API fails
                console.log('Falling back to page reload...');
                const url = new URL(window.location.href);
                url.searchParams.set('_refresh', Date.now().toString());
                window.location.href = url.toString();
            });
        },
        
        /**
         * Update dashboard data with new API response
         */
        updateDashboardData: function(data) {
            // Update KPI cards
            this.updateKPICards(data);
            
            // Update charts
            this.updateCharts(data);
            
            // Show success indicator
            this.showRefreshIndicator();
        },
        
        /**
         * Update KPI cards with new data
         */
        updateKPICards: function(data) {
            // Format number with commas and no decimals
            const formatNumber = (num) => {
                if (!num && num !== 0) return '0';
                // Round to remove decimals, then format with commas
                const rounded = Math.round(parseFloat(num));
                return rounded.toLocaleString('en-IN', { maximumFractionDigits: 0 });
            };
            
            // Update Total Records
            const totalRecordsEl = document.querySelector('[data-kpi="total_records"]');
            if (totalRecordsEl && data.total_records !== undefined) {
                totalRecordsEl.textContent = formatNumber(data.total_records);
            }
            
            // Update Fresh/Reloan counts
            const freshCountEl = document.querySelector('[data-kpi="fresh_count"]');
            const reloanCountEl = document.querySelector('[data-kpi="reloan_count"]');
            if (freshCountEl && data.fresh_count !== undefined) {
                freshCountEl.textContent = formatNumber(data.fresh_count);
            }
            if (reloanCountEl && data.reloan_count !== undefined) {
                reloanCountEl.textContent = formatNumber(data.reloan_count);
            }
            
            // Update Total Loan Amount
            const totalLoanEl = document.querySelector('[data-kpi="total_loan_amount"]');
            if (totalLoanEl && data.total_loan_amount !== undefined) {
                totalLoanEl.textContent = '₹' + formatNumber(data.total_loan_amount);
            }
            
            // Update Total Disbursal Amount
            const totalDisbursalEl = document.querySelector('[data-kpi="total_disbursal_amount"]');
            if (totalDisbursalEl && data.total_disbursal_amount !== undefined) {
                totalDisbursalEl.textContent = '₹' + formatNumber(data.total_disbursal_amount);
            }
            
            // Update Processing Fee
            const processingFeeEl = document.querySelector('[data-kpi="processing_fee"]');
            if (processingFeeEl && data.processing_fee !== undefined) {
                processingFeeEl.textContent = '₹' + formatNumber(data.processing_fee);
            }
            
            // Update Interest Amount
            const interestAmountEl = document.querySelector('[data-kpi="interest_amount"]');
            if (interestAmountEl && data.interest_amount !== undefined) {
                interestAmountEl.textContent = '₹' + formatNumber(data.interest_amount);
            }
            
            // Update Repayment Amount
            const repaymentAmountEl = document.querySelector('[data-kpi="repayment_amount"]');
            if (repaymentAmountEl && data.repayment_amount !== undefined) {
                repaymentAmountEl.textContent = '₹' + formatNumber(data.repayment_amount);
            }
            
            // Update Average Tenure (rounded to no decimals)
            const avgTenureEl = document.querySelector('[data-kpi="average_tenure"]');
            if (avgTenureEl && data.average_tenure !== undefined) {
                avgTenureEl.textContent = Math.round(data.average_tenure);
            }
            
            // Update Fresh/Reloan amounts for all cards using data attributes
            // Total Loan Amount - Fresh/Reloan
            const freshLoanEl = document.querySelector('[data-kpi="fresh_loan_amount"]');
            const reloanLoanEl = document.querySelector('[data-kpi="reloan_loan_amount"]');
            if (freshLoanEl && data.fresh_loan_amount !== undefined) {
                freshLoanEl.textContent = '₹' + formatNumber(data.fresh_loan_amount);
            }
            if (reloanLoanEl && data.reloan_loan_amount !== undefined) {
                reloanLoanEl.textContent = '₹' + formatNumber(data.reloan_loan_amount);
            }
            
            // Total Disbursal Amount - Fresh/Reloan
            const freshDisbursalEl = document.querySelector('[data-kpi="fresh_disbursal_amount"]');
            const reloanDisbursalEl = document.querySelector('[data-kpi="reloan_disbursal_amount"]');
            if (freshDisbursalEl && data.fresh_disbursal_amount !== undefined) {
                freshDisbursalEl.textContent = '₹' + formatNumber(data.fresh_disbursal_amount);
            }
            if (reloanDisbursalEl && data.reloan_disbursal_amount !== undefined) {
                reloanDisbursalEl.textContent = '₹' + formatNumber(data.reloan_disbursal_amount);
            }
            
            // Processing Fee - Fresh/Reloan
            const freshProcFeeEl = document.querySelector('[data-kpi="fresh_processing_fee"]');
            const reloanProcFeeEl = document.querySelector('[data-kpi="reloan_processing_fee"]');
            if (freshProcFeeEl && data.fresh_processing_fee !== undefined) {
                freshProcFeeEl.textContent = '₹' + formatNumber(data.fresh_processing_fee);
            }
            if (reloanProcFeeEl && data.reloan_processing_fee !== undefined) {
                reloanProcFeeEl.textContent = '₹' + formatNumber(data.reloan_processing_fee);
            }
            
            // Interest Amount - Fresh/Reloan
            const freshInterestEl = document.querySelector('[data-kpi="fresh_interest_amount"]');
            const reloanInterestEl = document.querySelector('[data-kpi="reloan_interest_amount"]');
            if (freshInterestEl && data.fresh_interest_amount !== undefined) {
                freshInterestEl.textContent = '₹' + formatNumber(data.fresh_interest_amount);
            }
            if (reloanInterestEl && data.reloan_interest_amount !== undefined) {
                reloanInterestEl.textContent = '₹' + formatNumber(data.reloan_interest_amount);
            }
            
            // Repayment Amount - Fresh/Reloan
            const freshRepayEl = document.querySelector('[data-kpi="fresh_repayment_amount"]');
            const reloanRepayEl = document.querySelector('[data-kpi="reloan_repayment_amount"]');
            if (freshRepayEl && data.fresh_repayment_amount !== undefined) {
                freshRepayEl.textContent = '₹' + formatNumber(data.fresh_repayment_amount);
            }
            if (reloanRepayEl && data.reloan_repayment_amount !== undefined) {
                reloanRepayEl.textContent = '₹' + formatNumber(data.reloan_repayment_amount);
            }
            
            // Average Tenure - Fresh/Reloan (rounded to no decimals)
            const freshTenureEl = document.querySelector('[data-kpi="fresh_average_tenure"]');
            const reloanTenureEl = document.querySelector('[data-kpi="reloan_average_tenure"]');
            if (freshTenureEl && data.fresh_average_tenure !== undefined) {
                freshTenureEl.textContent = Math.round(data.fresh_average_tenure) + ' days';
            }
            if (reloanTenureEl && data.reloan_average_tenure !== undefined) {
                reloanTenureEl.textContent = Math.round(data.reloan_average_tenure) + ' days';
            }
            
            // Update Collection Metrics
            console.log('Checking for collection_metrics in data:', data);
            console.log('collection_metrics exists?', !!data.collection_metrics);
            console.log('collection_metrics value:', data.collection_metrics);
            
            if (data.collection_metrics && typeof data.collection_metrics === 'object') {
                console.log('Collection Metrics Data:', data.collection_metrics);
                console.log('Collection Metrics Keys:', Object.keys(data.collection_metrics));
                console.log('Collection Metrics Full Object:', JSON.stringify(data.collection_metrics, null, 2));
                
                // Get all collection metrics elements
                const elements = {
                    mainTotal: document.querySelector('[data-kpi="collection_total"]'),  // Main heading
                    total: document.querySelector('[data-kpi="collection_total_amount_display"]'),  // Breakdown total
                    freshAmount: document.querySelector('[data-kpi="collection_fresh_amount"]'),
                    reloanAmount: document.querySelector('[data-kpi="collection_reloan_amount"]'),
                    prepaymentAmount: document.querySelector('[data-kpi="collection_prepayment_amount"]'),
                    onTime: document.querySelector('[data-kpi="collection_on_time"]'),
                    overdue: document.querySelector('[data-kpi="collection_overdue"]'),
                    totalCount: document.querySelector('[data-kpi="collection_total_count"]'),
                    freshCount: document.querySelector('[data-kpi="collection_fresh_count"]'),
                    reloanCount: document.querySelector('[data-kpi="collection_reloan_count"]'),
                    prepaymentCount: document.querySelector('[data-kpi="collection_prepayment_count"]'),
                    dueDateCount: document.querySelector('[data-kpi="collection_due_date_count"]'),
                    overdueCount: document.querySelector('[data-kpi="collection_overdue_count"]')
                };
                
                // Debug: Log element selection
                console.log('Collection Metrics Elements:', {
                    mainTotal: elements.mainTotal ? 'Found' : 'NOT FOUND',
                    breakdownTotal: elements.total ? 'Found' : 'NOT FOUND',
                    freshAmount: elements.freshAmount ? 'Found' : 'NOT FOUND',
                    reloanAmount: elements.reloanAmount ? 'Found' : 'NOT FOUND'
                });
                
                const metrics = data.collection_metrics;
                
                // Helper function to get value with multiple field name fallbacks (case-insensitive)
                // IMPORTANT: For collection amounts, reject any field containing 'repayment' to avoid using repayment_amount
                function getValue(obj, ...fieldNames) {
                    if (!obj || typeof obj !== 'object') return 0;
                    
                    // First try exact matches
                    for (const fieldName of fieldNames) {
                        if (obj[fieldName] !== null && obj[fieldName] !== undefined && obj[fieldName] !== '') {
                            // Reject if field name contains 'repayment' (unless it's explicitly in the allowed list)
                            if (fieldName.toLowerCase().includes('repayment') && !fieldName.toLowerCase().includes('collection')) {
                                console.log(`[Collection Metrics JS] Rejecting '${fieldName}' - contains repayment`);
                                continue;
                            }
                            return obj[fieldName];
                        }
                    }
                    
                    // Then try case-insensitive matches
                    const objKeys = Object.keys(obj);
                    const lowerObjKeys = objKeys.map(k => k.toLowerCase());
                    
                    for (const fieldName of fieldNames) {
                        const lowerFieldName = fieldName.toLowerCase();
                        const index = lowerObjKeys.indexOf(lowerFieldName);
                        if (index !== -1) {
                            const actualKey = objKeys[index];
                            // Reject if actual key contains 'repayment' (unless it's explicitly a collection field)
                            if (actualKey.toLowerCase().includes('repayment') && !actualKey.toLowerCase().includes('collection')) {
                                console.log(`[Collection Metrics JS] Rejecting '${actualKey}' (case-insensitive match) - contains repayment`);
                                continue;
                            }
                            if (obj[actualKey] !== null && obj[actualKey] !== undefined && obj[actualKey] !== '') {
                                return obj[actualKey];
                            }
                        }
                    }
                    
                    return 0;
                }
                
                // Helper function to update element
                function updateElement(el, value, isAmount = true) {
                    if (el && value !== null && value !== undefined && value !== '') {
                        if (isAmount) {
                            el.textContent = '₹' + formatNumber(value);
                        } else {
                            // For counts, append " count" text
                            el.textContent = formatNumber(value) + ' count';
                        }
                        return true;
                    }
                    return false;
                }
                
                // Get Fresh and Reloan amounts first
                // IMPORTANT: ONLY use fresh_collection_amount and reloan_collection_amount - do not use repayment_amount or other variations
                const freshAmount = getValue(metrics, 'fresh_collection_amount', 'freshCollectionAmount') || 0;
                const reloanAmount = getValue(metrics, 'reloan_collection_amount', 'reloanCollectionAmount') || 0;
                
                // Calculate Total as Fresh + Reloan (always, even if total_collection_amount exists)
                const totalAmount = (parseFloat(freshAmount) || 0) + (parseFloat(reloanAmount) || 0);
                
                // Update all amount fields with multiple field name variations
                // Update the main heading total first
                if (elements.mainTotal) {
                    updateElement(elements.mainTotal, totalAmount);
                    console.log('✓ Updated main heading total:', totalAmount);
                } else {
                    console.log('⚠ Main total element not found');
                }
                // Update the breakdown total
                if (elements.total) {
                    updateElement(elements.total, totalAmount);
                    console.log('✓ Updated breakdown total:', totalAmount);
                } else {
                    console.log('⚠ Breakdown total element not found - trying alternative selector');
                    // Try alternative selector
                    const altTotal = document.querySelector('[data-kpi="collection_total_amount_display"]');
                    if (altTotal) {
                        updateElement(altTotal, totalAmount);
                        console.log('✓ Updated breakdown total (alternative):', totalAmount);
                    }
                }
                updateElement(elements.freshAmount, freshAmount);
                updateElement(elements.reloanAmount, reloanAmount);
                
                console.log('Collection amounts calculated:', {
                    fresh: freshAmount,
                    reloan: reloanAmount,
                    total: totalAmount,
                    'fresh + reloan': (parseFloat(freshAmount) || 0) + (parseFloat(reloanAmount) || 0)
                });
                
                // Get prepayment amount with multiple field name variations
                // Try to find prepayment_amount in the metrics object
                let prepaymentAmount = 0;
                if (metrics && typeof metrics === 'object') {
                    // Try exact matches first
                    if (metrics.prepayment_amount !== null && metrics.prepayment_amount !== undefined && metrics.prepayment_amount !== '') {
                        prepaymentAmount = parseFloat(metrics.prepayment_amount) || 0;
                        console.log('[Collection Metrics JS] Found prepayment_amount (exact):', prepaymentAmount);
                    } else if (metrics.prepaymentAmount !== null && metrics.prepaymentAmount !== undefined && metrics.prepaymentAmount !== '') {
                        prepaymentAmount = parseFloat(metrics.prepaymentAmount) || 0;
                        console.log('[Collection Metrics JS] Found prepaymentAmount (camelCase):', prepaymentAmount);
                    } else {
                        // Try case-insensitive search
                        const objKeys = Object.keys(metrics);
                        const lowerObjKeys = objKeys.map(k => k.toLowerCase());
                        const prepaymentKeys = ['prepayment_amount', 'prepaymentamount', 'prepayment', 'prepaymentamt', 'prepayment_amt'];
                        
                        for (const key of prepaymentKeys) {
                            const index = lowerObjKeys.indexOf(key.toLowerCase());
                            if (index !== -1) {
                                const actualKey = objKeys[index];
                                const value = metrics[actualKey];
                                if (value !== null && value !== undefined && value !== '') {
                                    prepaymentAmount = parseFloat(value) || 0;
                                    console.log(`[Collection Metrics JS] Found prepayment via case-insensitive match: '${actualKey}' = ${prepaymentAmount}`);
                                    break;
                                }
                            }
                        }
                    }
                }
                
                console.log('[Collection Metrics JS] Prepayment amount lookup result:', {
                    'metrics keys': metrics ? Object.keys(metrics) : 'metrics is null/undefined',
                    'prepayment_amount value': metrics?.prepayment_amount,
                    'prepaymentAmount value': metrics?.prepaymentAmount,
                    'prepayment value': metrics?.prepayment,
                    'final prepaymentAmount': prepaymentAmount
                });
                
                if (elements.prepaymentAmount) {
                    updateElement(elements.prepaymentAmount, prepaymentAmount);
                    console.log('[Collection Metrics JS] Updated prepaymentAmount element with value:', prepaymentAmount);
                } else {
                    console.log('[Collection Metrics JS] ERROR: prepaymentAmount element not found!');
                }
                updateElement(elements.onTime, getValue(metrics, 'due_date_amount', 'dueDateAmount', 'on_time_collection', 'onTimeCollection', 'on_time', 'onTime', 'on_time_amount', 'onTimeAmount', 'ontime', 'ontime_amount', 'ontimeAmount', 'onTime_amount', 'on_time_collection_amount', 'onTimeCollectionAmount', 'due_date_collection', 'dueDateCollection', 'on_time_amount_collection', 'onTimeAmountCollection'));
                updateElement(elements.overdue, getValue(metrics, 'overdue_amount', 'overdueAmount', 'overdue_collection', 'overdueCollection', 'overdue', 'overDue'));
                
                // Get Fresh and Reloan counts first
                const freshCount = getValue(metrics, 'fresh_collection_count', 'freshCollectionCount', 'fresh_count', 'freshCount', 'fresh') || 0;
                const reloanCount = getValue(metrics, 'reloan_collection_count', 'reloanCollectionCount', 'reloan_count', 'reloanCount', 'reloan') || 0;
                
                // Calculate Total count as Fresh + Reloan (always, even if total_collection_count exists)
                const totalCount = (parseInt(freshCount) || 0) + (parseInt(reloanCount) || 0);
                
                // Update all count fields with multiple field name variations
                updateElement(elements.totalCount, totalCount, false);
                updateElement(elements.freshCount, freshCount, false);
                updateElement(elements.reloanCount, reloanCount, false);
                // Get prepayment count with explicit lookup (similar to prepayment_amount)
                let prepaymentCount = 0;
                if (metrics && typeof metrics === 'object') {
                    // Try exact matches first
                    if (metrics.prepayment_count !== null && metrics.prepayment_count !== undefined && metrics.prepayment_count !== '') {
                        prepaymentCount = parseInt(metrics.prepayment_count) || 0;
                        console.log('[Collection Metrics JS] Found prepayment_count (exact):', prepaymentCount);
                    } else if (metrics.prepaymentCount !== null && metrics.prepaymentCount !== undefined && metrics.prepaymentCount !== '') {
                        prepaymentCount = parseInt(metrics.prepaymentCount) || 0;
                        console.log('[Collection Metrics JS] Found prepaymentCount (camelCase):', prepaymentCount);
                    } else {
                        // Try case-insensitive search
                        const objKeys = Object.keys(metrics);
                        const lowerObjKeys = objKeys.map(k => k.toLowerCase());
                        const prepaymentCountKeys = ['prepayment_count', 'prepaymentcount', 'prepaymentcnt', 'prepayment_cnt'];
                        
                        for (const key of prepaymentCountKeys) {
                            const index = lowerObjKeys.indexOf(key.toLowerCase());
                            if (index !== -1) {
                                const actualKey = objKeys[index];
                                const value = metrics[actualKey];
                                if (value !== null && value !== undefined && value !== '') {
                                    prepaymentCount = parseInt(value) || 0;
                                    console.log(`[Collection Metrics JS] Found prepayment_count via case-insensitive match: '${actualKey}' = ${prepaymentCount}`);
                                    break;
                                }
                            }
                        }
                    }
                }
                
                console.log('[Collection Metrics JS] Prepayment count lookup result:', {
                    'prepayment_count value': metrics?.prepayment_count,
                    'prepaymentCount value': metrics?.prepaymentCount,
                    'final prepaymentCount': prepaymentCount
                });
                
                if (elements.prepaymentCount) {
                    updateElement(elements.prepaymentCount, prepaymentCount, false);
                    console.log('[Collection Metrics JS] Updated prepaymentCount element with value:', prepaymentCount);
                } else {
                    console.log('[Collection Metrics JS] ERROR: prepaymentCount element not found!');
                }
                updateElement(elements.dueDateCount, getValue(metrics, 'due_date_count', 'dueDateCount', 'on_time_count', 'onTimeCount', 'onTime', 'ontime', 'ontime_count', 'onTime_count', 'on_time_collection_count', 'onTimeCollectionCount', 'due_date_collection_count', 'dueDateCollectionCount'), false);
                updateElement(elements.overdueCount, getValue(metrics, 'overdue_count', 'overdueCount', 'overdue'), false);
                
                console.log('✓ Updated all Collection Metrics fields');
                // Get prepayment amount (already calculated above)
                const prepaymentValue = prepaymentAmount; // Use the value we already calculated
                const onTimeValue = getValue(metrics, 'due_date_amount', 'dueDateAmount', 'on_time_collection', 'onTimeCollection', 'on_time', 'onTime', 'on_time_amount', 'onTimeAmount', 'ontime', 'ontime_amount', 'ontimeAmount', 'onTime_amount', 'on_time_collection_amount', 'onTimeCollectionAmount', 'due_date_collection', 'dueDateCollection', 'on_time_amount_collection', 'onTimeAmountCollection');
                const overdueValue = getValue(metrics, 'overdue_amount', 'overdueAmount', 'overdue_collection', 'overdueCollection', 'overdue', 'overDue');
                console.log('Collection Metrics Summary:', {
                    total: totalAmount + ' (calculated as Fresh + Reloan)',
                    fresh: freshAmount,
                    reloan: reloanAmount,
                    prepayment: prepaymentValue,
                    prepaymentCount: prepaymentCount,
                    onTime: onTimeValue,
                    overdue: overdueValue
                });
                console.log('[Collection Metrics JS] Full metrics object:', metrics);
            } else {
                console.log('No collection_metrics found in data or it is not an object');
                console.log('Full data object keys:', Object.keys(data));
                console.log('Data object:', data);
            }
            
            console.log('KPI cards updated successfully');
        },
        
        /**
         * Update charts with new data
         */
        updateCharts: function(data) {
            console.log('Updating charts with data:', data);
            
            // Parse JSON strings if needed
            let stateLabels = data.state_labels;
            let stateValues = data.state_values;
            let stateSanction = data.state_sanction;
            let stateCounts = data.state_counts;
            let cityLabels = data.city_labels;
            let cityValues = data.city_values;
            let citySanction = data.city_sanction;
            let cityCounts = data.city_counts;
            let sourceLabels = data.source_labels;
            let sourceValues = data.source_values;
            let sourceSanction = data.source_sanction;
            let sourceCounts = data.source_counts;
            
            // If data is JSON string, parse it
            if (typeof stateLabels === 'string') {
                try {
                    stateLabels = JSON.parse(stateLabels);
                    stateValues = JSON.parse(stateValues);
                    stateSanction = JSON.parse(stateSanction);
                    if (stateCounts) stateCounts = typeof stateCounts === 'string' ? JSON.parse(stateCounts) : stateCounts;
                } catch (e) {
                    console.error('Error parsing state data:', e);
                }
            }
            if (typeof cityLabels === 'string') {
                try {
                    cityLabels = JSON.parse(cityLabels);
                    cityValues = JSON.parse(cityValues);
                    citySanction = JSON.parse(citySanction);
                    if (cityCounts) cityCounts = typeof cityCounts === 'string' ? JSON.parse(cityCounts) : cityCounts;
                } catch (e) {
                    console.error('Error parsing city data:', e);
                }
            }
            if (typeof sourceLabels === 'string') {
                try {
                    sourceLabels = JSON.parse(sourceLabels);
                    sourceValues = JSON.parse(sourceValues);
                    sourceSanction = JSON.parse(sourceSanction);
                    if (sourceCounts) sourceCounts = typeof sourceCounts === 'string' ? JSON.parse(sourceCounts) : sourceCounts;
                } catch (e) {
                    console.error('Error parsing source data:', e);
                }
            }
            
            // Update state chart
            if (stateLabels && stateValues && stateLabels.length > 0 && stateValues.length > 0) {
                // Update global data object for tooltip callbacks
                window.stateData = { labels: stateLabels, values: stateValues, sanction: stateSanction || [], counts: stateCounts || [] };
                
                if (typeof window.stateChart !== 'undefined' && window.stateChart) {
                    console.log('Updating state chart');
                    window.stateChart.data.labels = stateLabels;
                    window.stateChart.data.datasets[0].data = stateValues;
                    if (stateSanction) {
                        window.stateChart.data.sanction = stateSanction;
                    }
                    if (stateCounts) {
                        window.stateChart.data.counts = stateCounts;
                    }
                    // Update colors if needed
                    const chartColors = window.chartColors || [
                        '#3b82f6', '#10b981', '#f59e0b', '#ec4899', '#06b6d4', '#8b5cf6',
                        '#ef4444', '#84cc16', '#f97316', '#14b8a6', '#a855f7', '#eab308'
                    ];
                    window.stateChart.data.datasets[0].backgroundColor = chartColors.slice(0, stateLabels.length);
                    window.stateChart.update('none');
                    
                    // Update legend if function exists
                    if (typeof window.renderCustomLegend === 'function' && stateSanction) {
                        window.renderCustomLegend('stateLegend', stateLabels, stateValues, 
                            window.stateChart.data.datasets[0].backgroundColor, stateSanction, stateCounts);
                    }
                } else {
                    console.warn('State chart not found, attempting to initialize...');
                    if (typeof window.initializeCharts === 'function') {
                        // Update global data first
                        window.stateData = { labels: stateLabels, values: stateValues, sanction: stateSanction, counts: stateCounts || [] };
                        window.initializeCharts();
                    }
                }
            }
            
            // Update city chart
            if (cityLabels && cityValues && cityLabels.length > 0 && cityValues.length > 0) {
                // Update global data object for tooltip callbacks
                window.cityData = { labels: cityLabels, values: cityValues, sanction: citySanction || [], counts: cityCounts || [] };
                
                if (typeof window.cityChart !== 'undefined' && window.cityChart) {
                    console.log('Updating city chart');
                    window.cityChart.data.labels = cityLabels;
                    window.cityChart.data.datasets[0].data = cityValues;
                    if (citySanction) {
                        window.cityChart.data.sanction = citySanction;
                    }
                    if (cityCounts) {
                        window.cityChart.data.counts = cityCounts;
                    }
                    // Update colors if needed
                    const chartColors = window.chartColors || [
                        '#3b82f6', '#10b981', '#f59e0b', '#ec4899', '#06b6d4', '#8b5cf6',
                        '#ef4444', '#84cc16', '#f97316', '#14b8a6', '#a855f7', '#eab308'
                    ];
                    window.cityChart.data.datasets[0].backgroundColor = chartColors.slice(0, cityLabels.length);
                    window.cityChart.update('none');
                    
                    // Update legend if function exists
                    if (typeof window.renderCustomLegend === 'function' && citySanction) {
                        window.renderCustomLegend('cityLegend', cityLabels, cityValues,
                            window.cityChart.data.datasets[0].backgroundColor, citySanction, cityCounts);
                    }
                } else {
                    console.warn('City chart not found, attempting to initialize...');
                    if (typeof window.initializeCharts === 'function') {
                        // Update global data first
                        window.cityData = { labels: cityLabels, values: cityValues, sanction: citySanction, counts: cityCounts || [] };
                        window.initializeCharts();
                    }
                }
            }
            
            // Update source chart
            if (sourceLabels && sourceValues && sourceLabels.length > 0 && sourceValues.length > 0) {
                // Update global data object for tooltip callbacks
                window.sourceData = { labels: sourceLabels, values: sourceValues, sanction: sourceSanction || [], counts: sourceCounts || [] };
                
                if (typeof window.sourceChart !== 'undefined' && window.sourceChart) {
                    console.log('Updating source chart');
                    window.sourceChart.data.labels = sourceLabels;
                    window.sourceChart.data.datasets[0].data = sourceValues;
                    if (sourceSanction) {
                        window.sourceChart.data.sanction = sourceSanction;
                    }
                    if (sourceCounts) {
                        window.sourceChart.data.counts = sourceCounts;
                    }
                    // Update colors if needed
                    const chartColors = window.chartColors || [
                        '#3b82f6', '#10b981', '#f59e0b', '#ec4899', '#06b6d4', '#8b5cf6',
                        '#ef4444', '#84cc16', '#f97316', '#14b8a6', '#a855f7', '#eab308'
                    ];
                    window.sourceChart.data.datasets[0].backgroundColor = chartColors.slice(0, sourceLabels.length);
                    window.sourceChart.update('none');
                    
                    // Update legend if function exists
                    if (typeof window.renderCustomLegend === 'function' && sourceSanction) {
                        window.renderCustomLegend('sourceLegend', sourceLabels, sourceValues,
                            window.sourceChart.data.datasets[0].backgroundColor, sourceSanction, sourceCounts);
                    }
                } else {
                    console.warn('Source chart not found, attempting to initialize...');
                    if (typeof window.initializeCharts === 'function') {
                        // Update global data first
                        window.sourceData = { labels: sourceLabels, values: sourceValues, sanction: sourceSanction, counts: sourceCounts || [] };
                        window.initializeCharts();
                    }
                }
            }
        },
        
        /**
         * Show refresh indicator
         */
        showRefreshIndicator: function() {
            const indicator = document.getElementById('refresh-indicator');
            if (indicator) {
                indicator.classList.remove('hidden');
                setTimeout(() => {
                    indicator.classList.add('hidden');
                }, 2000);
            }
        },
        
        /**
         * Update last updated timestamp
         */
        updateLastUpdated: function() {
            const lastUpdatedEl = document.getElementById('last-updated-time');
            if (!lastUpdatedEl) return;
            
            const now = new Date();
            const timeString = now.toLocaleTimeString('en-US', {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
            
            lastUpdatedEl.textContent = timeString;
        },
        
        /**
         * Setup mobile sidebar toggle
         */
        setupMobileSidebar: function() {
            // Function is defined in sidebar template, but we can enhance it here
            window.toggleMobileSidebar = function() {
                const sidebar = document.getElementById('mobile-sidebar');
                if (sidebar) {
                    sidebar.classList.toggle('hidden');
                }
            };
        },
        
        /**
         * Setup HTMX event listeners
         */
        setupHTMX: function() {
            if (typeof htmx === 'undefined') return;
            
            // Handle HTMX after swap to reinitialize charts
            document.body.addEventListener('htmx:afterSwap', (event) => {
                // Reinitialize charts if they exist
                if (typeof initializeCharts === 'function') {
                    initializeCharts();
                }
                
                // Update active filters
                if (typeof updateActiveFilters === 'function') {
                    updateActiveFilters();
                }
            });
            
            // Show loading state during HTMX requests
            document.body.addEventListener('htmx:beforeRequest', () => {
                this.showLoadingState();
            });
            
            document.body.addEventListener('htmx:afterRequest', () => {
                this.hideLoadingState();
            });
        },
        
        /**
         * Show loading state
         */
        showLoadingState: function() {
            // Add loading overlay or skeleton
            const loadingOverlay = document.createElement('div');
            loadingOverlay.id = 'dashboard-loading';
            loadingOverlay.className = 'fixed inset-0 bg-slate-950/50 backdrop-blur-sm z-50 flex items-center justify-center';
            loadingOverlay.innerHTML = `
                <div class="flex flex-col items-center gap-4">
                    <div class="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
                    <p class="text-slate-300 text-sm">Refreshing data...</p>
                </div>
            `;
            document.body.appendChild(loadingOverlay);
        },
        
        /**
         * Hide loading state
         */
        hideLoadingState: function() {
            const loadingOverlay = document.getElementById('dashboard-loading');
            if (loadingOverlay) {
                loadingOverlay.remove();
            }
        },
        
        /**
         * Register chart instance
         */
        registerChart: function(name, chartInstance) {
            this.charts[name] = chartInstance;
        },
        
        /**
         * Get chart instance
         */
        getChart: function(name) {
            return this.charts[name];
        },
        
        /**
         * Destroy all charts
         */
        destroyCharts: function() {
            Object.values(this.charts).forEach(chart => {
                if (chart && typeof chart.destroy === 'function') {
                    chart.destroy();
                }
            });
            this.charts = {};
        }
    };
    
    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => Dashboard.init());
    } else {
        Dashboard.init();
    }
    
    // Export to global scope for use in templates
    window.Dashboard = Dashboard;
    
    /**
     * Theme Toggle Function
     */
    window.toggleTheme = function() {
        const html = document.documentElement;
        const currentTheme = html.classList.contains('dark') ? 'dark' : 'light';
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        
        // Toggle dark class
        html.classList.toggle('dark', newTheme === 'dark');
        document.getElementById('html-root').setAttribute('data-theme', newTheme);
        
        // Save to localStorage
        localStorage.setItem('theme', newTheme);
        
        // Update chart tooltips if charts exist
        if (typeof stateChart !== 'undefined' && stateChart) {
            stateChart.options.plugins.tooltip.backgroundColor = newTheme === 'dark' 
                ? 'rgba(15, 23, 42, 0.95)' 
                : 'rgba(255, 255, 255, 0.95)';
            stateChart.options.plugins.tooltip.titleColor = newTheme === 'dark' 
                ? '#f1f5f9' 
                : '#111827';
            stateChart.options.plugins.tooltip.bodyColor = newTheme === 'dark' 
                ? '#cbd5e1' 
                : '#374151';
            stateChart.options.plugins.tooltip.borderColor = newTheme === 'dark' 
                ? '#334155' 
                : '#e5e7eb';
            stateChart.update();
        }
        
        if (typeof cityChart !== 'undefined' && cityChart) {
            cityChart.options.plugins.tooltip.backgroundColor = newTheme === 'dark' 
                ? 'rgba(15, 23, 42, 0.95)' 
                : 'rgba(255, 255, 255, 0.95)';
            cityChart.options.plugins.tooltip.titleColor = newTheme === 'dark' 
                ? '#f1f5f9' 
                : '#111827';
            cityChart.options.plugins.tooltip.bodyColor = newTheme === 'dark' 
                ? '#cbd5e1' 
                : '#374151';
            cityChart.options.plugins.tooltip.borderColor = newTheme === 'dark' 
                ? '#334155' 
                : '#e5e7eb';
            cityChart.update();
        }
    };
    
    // Utility function for downloading charts
    window.downloadChart = function(chartId) {
        const chart = Dashboard.getChart(chartId);
        if (chart && typeof chart.toBase64Image === 'function') {
            const url = chart.toBase64Image();
            const link = document.createElement('a');
            link.download = `${chartId}_${new Date().toISOString().split('T')[0]}.png`;
            link.href = url;
            link.click();
        }
    };
    
    // Utility function for formatting currency
    window.formatCurrency = function(amount) {
        return new Intl.NumberFormat('en-IN', {
            style: 'currency',
            currency: 'INR',
            maximumFractionDigits: 0
        }).format(amount);
    };
    
    // Utility function for formatting numbers with commas
    window.formatNumber = function(num) {
        return new Intl.NumberFormat('en-IN').format(num);
    };
    
    /**
     * Sidebar Toggle Function
     */
    window.toggleSidebar = function() {
        const sidebar = document.getElementById('sidebar');
        const mainContentWrapper = document.getElementById('main-content-wrapper');
        const sidebarTitle = document.getElementById('sidebar-title');
        const sidebarTexts = document.querySelectorAll('.sidebar-text');
        const toggleIcon = document.getElementById('sidebar-toggle-icon');
        const isCollapsed = sidebar.style.width === '5rem' || sidebar.classList.contains('collapsed');
        
        // Check if we're on a large screen (lg breakpoint = 1024px)
        const isLargeScreen = window.innerWidth >= 1024;
        
        if (!isLargeScreen) {
            // On mobile/tablet, don't modify margins
            return;
        }
        
        if (isCollapsed) {
            // Expand sidebar
            sidebar.style.width = '16rem';
            sidebar.classList.remove('collapsed');
            if (mainContentWrapper) {
                // Remove inline styles to let Tailwind class (lg:ml-64) handle it
                mainContentWrapper.style.marginLeft = '';
                mainContentWrapper.style.width = '';
            }
            if (sidebarTitle) {
                sidebarTitle.style.opacity = '1';
                sidebarTitle.style.display = 'block';
            }
            sidebarTexts.forEach(text => {
                text.style.opacity = '1';
                text.style.display = 'block';
            });
            if (toggleIcon) {
                toggleIcon.style.transform = 'rotate(0deg)';
            }
            localStorage.setItem('sidebar-collapsed', 'false');
        } else {
            // Collapse sidebar
            sidebar.style.width = '5rem';
            sidebar.classList.add('collapsed');
            if (mainContentWrapper) {
                mainContentWrapper.style.marginLeft = '5rem';
                mainContentWrapper.style.width = 'calc(100% - 5rem)';
            }
            if (sidebarTitle) {
                sidebarTitle.style.opacity = '0';
                sidebarTitle.style.display = 'none';
            }
            sidebarTexts.forEach(text => {
                text.style.opacity = '0';
                text.style.display = 'none';
            });
            if (toggleIcon) {
                toggleIcon.style.transform = 'rotate(180deg)';
            }
            localStorage.setItem('sidebar-collapsed', 'true');
        }
    };
    
    // Initialize sidebar state on page load
    document.addEventListener('DOMContentLoaded', function() {
        const sidebar = document.getElementById('sidebar');
        const mainContentWrapper = document.getElementById('main-content-wrapper');
        const isCollapsed = localStorage.getItem('sidebar-collapsed') === 'true';
        
        if (!sidebar || !mainContentWrapper) return;
        
        // Check if we're on a large screen (lg breakpoint = 1024px)
        const isLargeScreen = window.innerWidth >= 1024;
        
        // Set initial sidebar and main content state
        if (isCollapsed && isLargeScreen) {
            sidebar.style.width = '5rem';
            sidebar.classList.add('collapsed');
            mainContentWrapper.style.marginLeft = '5rem';
            mainContentWrapper.style.width = 'calc(100% - 5rem)';
            
            const sidebarTitle = document.getElementById('sidebar-title');
            const sidebarTexts = document.querySelectorAll('.sidebar-text');
            const toggleIcon = document.getElementById('sidebar-toggle-icon');
            
            if (sidebarTitle) {
                sidebarTitle.style.opacity = '0';
                sidebarTitle.style.display = 'none';
            }
            sidebarTexts.forEach(text => {
                text.style.opacity = '0';
                text.style.display = 'none';
            });
            if (toggleIcon) {
                toggleIcon.style.transform = 'rotate(180deg)';
            }
        } else if (isLargeScreen) {
            // Expanded state on large screens - let Tailwind handle it
            sidebar.style.width = '16rem';
            sidebar.classList.remove('collapsed');
            // Don't set inline styles - let lg:ml-64 class handle the margin
            mainContentWrapper.style.marginLeft = '';
            mainContentWrapper.style.width = '';
        }
        // On small screens, let Tailwind handle the layout (no inline styles)
    });
    
})();

