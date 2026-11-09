# Huawei DDS and OBS handoff

The web service is already configured to read these values from `/srv/crackedwall/.env`.
Do not commit that file or paste its secrets into chat.

## DDS

1. In Huawei Cloud, create a **Document Database Service (DDS)** instance compatible with MongoDB in the same VPC and availability zone as the ECS.
2. Create the database user `crack_app` with read/write access only to `drone_crack`.
3. In the DDS security group/whitelist, permit the ECS **private IP** (`172.31.1.45` at deployment time), never `0.0.0.0/0`.
4. Copy the MongoDB-compatible connection string supplied by DDS to `MONGO_URI` in `/srv/crackedwall/.env`, then set:

```env
DB_NAME=drone_crack
COLLECTION_NAME=detections
```

5. Apply it without exposing the URI:

```bash
sudo systemctl restart crackedwall.service
sudo docker logs --tail 50 crackedwall-web
```

The service creates its timestamp/source/status indexes when it successfully connects.

## OBS

Create a private OBS bucket in the same region. Do not make evidence images public.
For a first release, evidence files are persisted in Docker volume `crackedwall_crackedwall-evidence` and served only after dashboard login. Add OBS access keys only when the storage integration is enabled; use an IAM user scoped to the single bucket, not the account owner credentials.

## Credentials

The initial dashboard credential is stored only on the server:

```bash
sudo cat /root/crackedwall-initial-admin.txt
```

Immediately replace `ADMIN_PASSWORD` and `SESSION_SECRET` in `/srv/crackedwall/.env`, then restart the service. A password hash can be used instead of plaintext `ADMIN_PASSWORD`.
