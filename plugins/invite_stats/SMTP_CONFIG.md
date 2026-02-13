# SMTP邮件发送配置说明

## 📧 功能说明

导出统计功能现在通过SMTP邮件发送，文件将作为附件发送到指定邮箱。

## ⚙️ 配置方法

### 1. 通过Web UI配置

访问框架Web UI，进入插件配置页面，找到 `invite_stats` 插件，配置以下参数：

- **smtp_host**: SMTP服务器地址
  - QQ邮箱：`smtp.qq.com`
  - 163邮箱：`smtp.163.com`
  - Gmail：`smtp.gmail.com`
  - 其他邮箱请查看对应服务商的SMTP设置

- **smtp_port**: SMTP端口
  - TLS：`587`（推荐）
  - SSL：`465`

- **smtp_user**: SMTP用户名（通常是邮箱地址）

- **smtp_password**: SMTP密码
  - QQ邮箱：需要使用**授权码**（不是QQ密码）
  - 163邮箱：需要使用**授权码**
  - Gmail：需要使用**应用专用密码**

- **smtp_from**: 发件人邮箱地址（通常与smtp_user相同）

- **smtp_to**: 收件人邮箱地址（导出统计将发送到此邮箱）

### 2. 直接编辑数据库

如果需要直接编辑配置，可以修改 `data/framework.db` 中的插件配置。

## 📋 常见邮箱SMTP配置

### QQ邮箱

```
smtp_host: smtp.qq.com
smtp_port: 587
smtp_user: 你的QQ邮箱（如：123456789@qq.com）
smtp_password: 授权码（需要在QQ邮箱设置中生成）
smtp_from: 你的QQ邮箱
smtp_to: 收件人邮箱
```

**获取QQ邮箱授权码**：
1. 登录QQ邮箱
2. 设置 → 账户
3. 开启"POP3/SMTP服务"
4. 生成授权码
5. 复制授权码作为 `smtp_password`

### 163邮箱

```
smtp_host: smtp.163.com
smtp_port: 587
smtp_user: 你的163邮箱
smtp_password: 授权码
smtp_from: 你的163邮箱
smtp_to: 收件人邮箱
```

### Gmail

```
smtp_host: smtp.gmail.com
smtp_port: 587
smtp_user: 你的Gmail地址
smtp_password: 应用专用密码
smtp_from: 你的Gmail地址
smtp_to: 收件人邮箱
```

## 🔧 工作原理

1. **生成文件**：统计数据保存为TXT文件
2. **发送邮件**：通过SMTP将文件作为附件发送
3. **降级方案**：如果邮件发送失败，自动降级为分段发送消息

## ⚠️ 注意事项

1. **授权码安全**：授权码相当于邮箱密码，请妥善保管
2. **端口选择**：
   - 端口587使用TLS加密（推荐）
   - 端口465使用SSL加密
3. **防火墙**：确保服务器可以访问SMTP服务器的端口
4. **测试**：配置完成后，建议先测试发送，确保配置正确

## 🐛 故障排除

### 邮件发送失败

1. **检查配置**：确认所有SMTP配置项都已填写
2. **检查授权码**：QQ/163邮箱必须使用授权码，不能使用登录密码
3. **检查端口**：确认端口号正确（587或465）
4. **检查网络**：确认服务器可以访问SMTP服务器
5. **查看日志**：检查框架日志中的详细错误信息

### 常见错误

- **"535 Error: authentication failed"**：授权码错误
- **"Connection refused"**：端口或服务器地址错误
- **"Timeout"**：网络问题或防火墙阻止

## 📊 使用示例

配置完成后，管理员（QQ: 3302727375）发送私聊消息：

```
导出统计
```

系统将：
1. 生成统计数据文件
2. 通过SMTP发送到配置的邮箱
3. 发送QQ消息确认："✅ 统计数据已通过邮件发送！请查收邮箱。"

