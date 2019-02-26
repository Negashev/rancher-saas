# rancher-saas
Up service with large data (for example mysql with 10gb storage) by nfs force

client contaner
```yaml
version: '2'

services:
  mariadb:
    image: negash/rancher-saas:client
    ports:
      - 3306:3306
    environment:
      PROXY_ADDR: tcp://0.0.0.0:3306
      SAAS_DELIVERY_URL: mysql.saas.server.ru
      SAAS_DELIVERY_PORT: 80
      PING_TIME: 600
```

![SaaS for everythink](SaaS.jpg?raw=true "SaaS")
[![FOSSA Status](https://app.fossa.io/api/projects/git%2Bgithub.com%2FNegashev%2Francher-saas.svg?type=shield)](https://app.fossa.io/projects/git%2Bgithub.com%2FNegashev%2Francher-saas?ref=badge_shield)



my mysql saas exmaple

![My mysql saas exmaple](my-saas-example.png?raw=true "My SaaS")


## License
[![FOSSA Status](https://app.fossa.io/api/projects/git%2Bgithub.com%2FNegashev%2Francher-saas.svg?type=large)](https://app.fossa.io/projects/git%2Bgithub.com%2FNegashev%2Francher-saas?ref=badge_large)