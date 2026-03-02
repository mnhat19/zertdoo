// Service Worker cho Zertdoo Web Push Notifications
// File nay can duoc phuc vu tu root path: /sw.js
// De Service Worker co scope / (toan bo origin)

self.addEventListener("install", (event) => {
    self.skipWaiting();
});

self.addEventListener("activate", (event) => {
    event.waitUntil(clients.claim());
});

// Xu ly push event tu server
self.addEventListener("push", (event) => {
    let data = {};
    if (event.data) {
        try {
            data = event.data.json();
        } catch (e) {
            data = { title: "Zertdoo", body: event.data.text() };
        }
    }

    const title = data.title || "Zertdoo";
    const options = {
        body: data.body || "",
        // Tag giong nhau se ghi de notification cu (tranh spam)
        tag: "zertdoo-sync",
        renotify: true,
        requireInteraction: false,
        silent: false,
        data: { url: "/dashboard" },
    };

    event.waitUntil(self.registration.showNotification(title, options));
});

// Click vao notification -> mo hoac focus dashboard
self.addEventListener("notificationclick", (event) => {
    event.notification.close();

    event.waitUntil(
        clients
            .matchAll({ type: "window", includeUncontrolled: true })
            .then((clientList) => {
                for (const client of clientList) {
                    if (client.url.includes("/dashboard") && "focus" in client) {
                        return client.focus();
                    }
                }
                if (clients.openWindow) {
                    return clients.openWindow("/dashboard");
                }
            })
    );
});
