from django.utils.deprecation import MiddlewareMixin

class AdminSidebarMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        if (request.path.startswith('/admin/') and request.path != '/admin/' and 
            hasattr(response, 'content') and 
            response.get('Content-Type', '').startswith('text/html')):
            
            try:
                content = response.content.decode('utf-8')
                
                if 'custom-sidebar' not in content and '<body' in content:
                    sidebar_html = '''
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>
    * { box-sizing: border-box !important; }
    html, body { margin: 0 !important; padding: 0 !important; }
    
    /* Hide Django defaults */
    #nav-sidebar, .toggle-nav-sidebar { display: none !important; }
    #branding { display: none !important; }
    
    /* Hide Django's theme toggle */
    .theme-toggle, button[title*="theme"], button[title*="Theme"],
    label.toggle-theme, .theme-switcher, a[href*="theme"] { display: none !important; }
    
    /* Hide the filter sidebar */
    #changelist-filter { display: none !important; }
    
    /* Make content full width when filter is hidden */
    #changelist { margin-right: 0 !important; width: 100% !important; }
    
    /* Custom sidebar */
    #custom-sidebar { 
        position: fixed;
        left: 0;
        top: 0;
        width: 250px;
        height: 100vh;
        z-index: 9999;
        overflow-y: auto;
        padding: 0;
        box-shadow: 2px 0 5px rgba(0,0,0,0.3);
    }
    
    #custom-sidebar .brand { 
        padding: 20px;
        font-size: 20px;
        font-weight: 600;
        color: #fff;
        text-align: center;
        border-bottom: 1px solid rgba(255,255,255,0.1);
        margin-bottom: 10px;
    }
    
    #custom-sidebar h2 { 
        padding: 0 20px; 
        font-size: 12px; 
        text-transform: uppercase; 
        margin: 20px 0 10px 0; 
        letter-spacing: 1px; 
        font-weight: 600; 
    }
    
    #custom-sidebar ul { list-style: none; padding: 0; margin: 0; }
    
    #custom-sidebar a { 
        display: flex; 
        align-items: center; 
        gap: 10px; 
        padding: 12px 20px; 
        text-decoration: none; 
        border-left: 3px solid transparent; 
        transition: all 0.2s; 
    }
    
    #custom-sidebar i { width: 20px; font-size: 14px; }
    
    /* Theme toggle button */
    #theme-toggle { 
        position: fixed; 
        top: 10px; 
        right: 20px; 
        z-index: 10000; 
        background: #3498db; 
        color: white; 
        border: none; 
        padding: 10px 15px; 
        border-radius: 5px; 
        cursor: pointer; 
        font-size: 14px; 
        display: flex; 
        align-items: center; 
        gap: 8px; 
        transition: background 0.3s;
    }
    
    #theme-toggle:hover { background: #2980b9; }
    
    /* Dark mode styles */
    body.dark-mode { background: #1a1a1a !important; color: #e0e0e0 !important; }
    body.dark-mode #custom-sidebar { background: #252525; }
    body.dark-mode #custom-sidebar .brand { color: #fff; }
    body.dark-mode #custom-sidebar h2 { color: #888; }
    body.dark-mode #custom-sidebar a { color: #b0b0b0; }
    body.dark-mode #custom-sidebar a:hover { background: #2a2a2a; color: #3498db; border-left-color: #3498db; }
    body.dark-mode #content { background: #1a1a1a !important; }
    body.dark-mode .module { background: #252525 !important; border: 1px solid #333 !important; }
    body.dark-mode .module h2, body.dark-mode .module caption { background: #2a2a2a !important; color: #fff !important; }
    body.dark-mode table { background: #252525 !important; color: #e0e0e0 !important; }
    body.dark-mode thead th { background: #2a2a2a !important; color: #aaa !important; }
    body.dark-mode tbody tr { background: #252525 !important; }
    body.dark-mode tbody tr:hover { background: #2a2a2a !important; }
    body.dark-mode tbody td { color: #ccc !important; border-bottom: 1px solid #333 !important; }
    body.dark-mode input, body.dark-mode textarea, body.dark-mode select { 
        background: #2a2a2a !important; 
        color: #e0e0e0 !important; 
        border: 1px solid #444 !important; 
    }
    body.dark-mode .breadcrumbs { background: #2a2a2a !important; color: #ccc !important; }
    body.dark-mode .breadcrumbs a { color: #3498db !important; }
    body.dark-mode #header { background: #2c3e50 !important; }
    
    /* Light mode styles */
    body.light-mode { background: #fff !important; color: #333 !important; }
    body.light-mode #custom-sidebar { background: #f8f9fa; border-right: 1px solid #ddd; }
    body.light-mode #custom-sidebar .brand { color: #333; border-bottom-color: #ddd; }
    body.light-mode #custom-sidebar h2 { color: #666; }
    body.light-mode #custom-sidebar a { color: #495057; }
    body.light-mode #custom-sidebar a:hover { background: #e9ecef; color: #007bff; border-left-color: #007bff; }
    body.light-mode #content { background: #fff !important; }
    body.light-mode .module { background: #fff !important; border: 1px solid #ddd !important; }
    body.light-mode .module h2, body.light-mode .module caption { background: #f8f9fa !important; color: #333 !important; }
    body.light-mode table { background: #fff !important; color: #333 !important; }
    body.light-mode thead th { background: #f8f9fa !important; color: #666 !important; }
    body.light-mode tbody tr { background: #fff !important; }
    body.light-mode tbody tr:hover { background: #f8f9fa !important; }
    body.light-mode tbody td { color: #495057 !important; border-bottom: 1px solid #dee2e6 !important; }
    body.light-mode input, body.light-mode textarea, body.light-mode select { 
        background: #fff !important; 
        color: #495057 !important; 
        border: 1px solid #ced4da !important; 
    }
    body.light-mode .breadcrumbs { background: #f8f9fa !important; color: #495057 !important; }
    body.light-mode .breadcrumbs a { color: #007bff !important; }
</style>
<button id="theme-toggle" onclick="toggleTheme()">
    <i class="fas fa-moon" id="theme-icon"></i>
    <span id="theme-text">Dark Mode</span>
</button>
<div id="custom-sidebar">
    <div class="brand">Kirepanet ADMIN</div>
    <h2>HOTSPOT_API</h2>
    <ul>
        <li><a href="/admin/"><i class="fas fa-home"></i> Dashboard</a></li>
        <li><a href="/admin/hotspot_api/hotspotplan/"><i class="fas fa-wifi"></i> Hotspot Plans</a></li>
        <li><a href="/admin/hotspot_api/hotspotcustomer/"><i class="fas fa-users"></i> Hotspot Customers</a></li>
        <li><a href="/admin/hotspot_api/mpesatransaction/"><i class="fas fa-money-bill-wave"></i> M-Pesa Transactions</a></li>
        <li><a href="/admin/hotspot_api/voucher/"><i class="fas fa-ticket-alt"></i> Vouchers</a></li>
        <li><a href="/admin/hotspot_api/accesspoint/"><i class="fas fa-broadcast-tower"></i> Access Points</a></li>
        <li><a href="/admin/hotspot_api/device/"><i class="fas fa-mobile-alt"></i> Devices</a></li>
        <li><a href="/admin/hotspot_api/usagedata/"><i class="fas fa-chart-line"></i> Usage Sessions</a></li>
    </ul>
    <h2>AUTHENTICATION</h2>
    <ul>
        <li><a href="/admin/auth/user/"><i class="fas fa-user"></i> Users</a></li>
        <li><a href="/admin/auth/group/"><i class="fas fa-users-cog"></i> Groups</a></li>
    </ul>
</div>
<script>
function toggleTheme() {
    const body = document.body;
    const icon = document.getElementById('theme-icon');
    const text = document.getElementById('theme-text');
    
    if (body.classList.contains('dark-mode')) {
        body.classList.remove('dark-mode');
        body.classList.add('light-mode');
        icon.className = 'fas fa-sun';
        text.textContent = 'Light Mode';
        localStorage.setItem('adminTheme', 'light');
    } else {
        body.classList.remove('light-mode');
        body.classList.add('dark-mode');
        icon.className = 'fas fa-moon';
        text.textContent = 'Dark Mode';
        localStorage.setItem('adminTheme', 'dark');
    }
}

const savedTheme = localStorage.getItem('adminTheme') || 'dark';
if (savedTheme === 'dark') {
    document.body.classList.add('dark-mode');
} else {
    document.body.classList.add('light-mode');
    document.getElementById('theme-icon').className = 'fas fa-sun';
    document.getElementById('theme-text').textContent = 'Light Mode';
}

setTimeout(function() {
    document.querySelectorAll('body > *').forEach(function(el) {
        if (el.id !== 'custom-sidebar' && el.id !== 'theme-toggle') {
            el.style.marginLeft = '250px';
            el.style.width = 'calc(100% - 250px)';
        }
    });
}, 100);
</script>
'''
                    content = content.replace('<body', sidebar_html + '<body', 1)
                    response.content = content.encode('utf-8')
                    response['Content-Length'] = len(response.content)
            except:
                pass
        return response