# 🚀 OrkaFlow Backend - Guia de Execução

## 📂 Caminhos importantes

**Projeto:**
/home/tharles.cunha/Projects/orkaflow-backend

**Virtualenv:**
/home/tharles.cunha/Projects/orkaflow-backend/venv

**.env:**
/home/tharles.cunha/Projects/orkaflow-backend/.env

---

## 🌐 API

- URL local:
http://127.0.0.1:8000

- URL rede:
http://10.50.156.202:8000

- Swagger:
http://10.50.156.202:8000/docs

---

## ⚙️ Serviços

### API
/etc/systemd/system/orkaflow-api.service

### Workers
/etc/systemd/system/orkaflow-workers.service

---

## ▶️ Comandos

### Iniciar
sudo systemctl start orkaflow-api <br>
sudo systemctl start orkaflow-workers

### Parar
sudo systemctl stop orkaflow-api <br>
sudo systemctl stop orkaflow-workers

### Reiniciar
sudo systemctl restart orkaflow-api <br>
sudo systemctl restart orkaflow-workers

### Status
sudo systemctl status orkaflow-api <br>
sudo systemctl status orkaflow-workers

### Logs
journalctl -u orkaflow-api -f <br>
journalctl -u orkaflow-workers -f

---

## 🔄 Atualizar systemd
sudo systemctl daemon-reload

---

## 🔁 Auto start
sudo systemctl enable orkaflow-api <br>
sudo systemctl enable orkaflow-workers

---

## ❌ Remover serviço

sudo systemctl stop orkaflow-api <br>
sudo rm /etc/systemd/system/orkaflow-api.service <br>
sudo systemctl daemon-reload

---

## 🧪 Execução manual

### Carregar .env
set -a
source .env
set +a

### Rodar API
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

### Rodar workers
python -m app.workers.main

---

## 🔐 Dependências

sudo apt install unixodbc unixodbc-dev <br>
sudo ACCEPT_EULA=Y apt install msodbcsql18

---

## 🌍 Rede

### IP do servidor
hostname -I

### Liberar porta
sudo ufw allow 8000/tcp

---

## ⚠️ Observações

- Usa .env
- Não usar --reload em produção
- Ver logs em caso de erro

---

## ✅ Status esperado

Active: active (running)
