# AWS từ đầu: đăng ký → chạy ComfyUI trên GPU (dành cho bản production)

Demo hiện chạy trên RunPod ([runpod-setup.md](runpod-setup.md)). Tài liệu này dùng khi chuyển sang AWS.
Máy chuẩn: **g6e.2xlarge** (L40S 48 GB, 8 vCPU, 64 GiB RAM), us-east-1, 2.242 USD/giờ on-demand;
bật 1–3 giờ/ngày ≈ 83–218 USD/tháng gồm ổ EBS 200 GB.

## Bước 1 – Tài khoản và bảo mật

1. Tạo tài khoản theo [hướng dẫn AWS](https://docs.aws.amazon.com/accounts/latest/reference/manage-acct-creating.html):
   email (nên dùng email nhóm công ty), số điện thoại, thẻ thanh toán; Support plan **Basic**.
2. **Chọn gói Paid, không chọn Free.** Gói Free giới hạn dịch vụ và hết 6 tháng (hoặc hết credit) thì tài khoản
   bị treo, dữ liệu giữ 90 ngày rồi xoá ([FAQ](https://aws.amazon.com/free/free-tier-faqs/)). Lỡ chọn Free:
   Settings → Billing → Upgrade. Credit tối đa 200 USD cho tài khoản mới ([Free Tier](https://aws.amazon.com/free/))
   — AWS không nói rõ có trừ cho GPU, đừng tính vào ngân sách.
3. Bật **MFA cho root** ngay; AWS bắt buộc trong 35 ngày ([best practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/root-user-best-practices.html)).
4. Không tạo access key cho root; tạo user quản trị riêng và dùng user đó hằng ngày.
5. Cài trên Windows: [AWS CLI v2](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) và
   [Session Manager plugin](https://docs.aws.amazon.com/systems-manager/latest/userguide/install-plugin-windows.html)
   (`https://s3.amazonaws.com/session-manager-downloads/plugin/latest/windows/SessionManagerPluginSetup.exe`, quyền Admin).

## Bước 2 – Chặn chi phí, xin quota GPU

1. **Budgets** ([hướng dẫn](https://docs.aws.amazon.com/cost-management/latest/userguide/budget-templates.html)):
   Create budget → *Use a template* → **Monthly cost budget** → số tiền (vd 250 USD) + email. Chỉ cảnh báo, không tự tắt máy.
2. **Quota GPU**: tài khoản mới có **"Running On-Demand G and VT instances" = 0 vCPU**
   ([bảng quota](https://docs.aws.amazon.com/ec2/latest/instancetypes/ec2-instance-quotas.html)).
   Region us-east-1 → Service Quotas → Amazon EC2 → quota mã L-DB2E81BA → Request increase → **8**.
   Thời gian duyệt không công bố.

## Bước 3 – Tạo máy GPU

1. IAM → Roles → Create role → AWS service, use case EC2 → policy **AmazonSSMManagedInstanceCore** → tên `SSMInstanceProfile`
   ([hướng dẫn](https://docs.aws.amazon.com/systems-manager/latest/userguide/setup-instance-permissions.html)).
2. Lấy AMI "Deep Learning Base OSS Nvidia Driver GPU AMI (Ubuntu 22.04)"
   ([release notes](https://docs.aws.amazon.com/dlami/latest/devguide/aws-deep-learning-x86-base-gpu-ami-ubuntu-22-04.html)):
   ```powershell
   aws ssm get-parameter --region us-east-1 `
     --name /aws/service/deeplearning/ami/x86_64/base-oss-nvidia-driver-gpu-ubuntu-22.04/latest/ami-id `
     --query "Parameter.Value" --output text
   ```
3. Launch instance:

   | Mục | Chọn |
   | --- | --- |
   | AMI / type | AMI trên / **g6e.2xlarge** |
   | Key pair | Không cần (dùng Session Manager) |
   | Network | VPC mặc định, Auto-assign public IP **Enable** (không cần NAT Gateway) |
   | Security group | Mới, **không có inbound rule** |
   | Storage | gp3 **200 GiB** |
   | IAM instance profile | `SSMInstanceProfile` |
   | Shutdown behavior | **Stop** · Termination protection: Enable |

4. Connect → Session Manager → `nvidia-smi` phải thấy L40S. Không dùng Elastic IP (tính 0.005 USD/h kể cả không dùng).

## Bước 4 – Bật/tắt và tự tắt

```powershell
aws ec2 start-instances --instance-ids i-xxxx --region us-east-1
aws ec2 stop-instances  --instance-ids i-xxxx --region us-east-1
```

- Lớp 1: `infra/aws/idle_stop.sh` chạy cron 5 phút/lần, GPU rảnh + hàng đợi ComfyUI trống 30 phút → `shutdown` (→ Stop).
- Lớp 2 (dự phòng): CloudWatch alarm `CPUUtilization` < 5, period 1 giờ, 2 datapoint → *Stop this instance*;
  chạy một lần `aws iam create-service-linked-role --aws-service-name events.amazonaws.com`
  ([hướng dẫn](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/UsingAlarmActions.html)).

## Bước 5 – ComfyUI

Cài ComfyUI + repo vào `/opt/furniture-ai`, chạy bằng `infra/aws/comfyui.service` (chỉ nghe 127.0.0.1).
Mở từ Windows qua port forwarding ([docs](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-sessions-start.html)):

```powershell
aws ssm start-session --region us-east-1 --target i-xxxx `
  --document-name AWS-StartPortForwardingSession `
  --parameters portNumber="8188",localPortNumber="8188"
```

Rồi mở `http://localhost:8188`.

## Checklist

- [ ] Gói Paid, root có MFA, dùng user quản trị
- [ ] Budgets gửi mail thử được
- [ ] Quota G and VT ≥ 8 vCPU ở us-east-1
- [ ] `nvidia-smi` thấy L40S; security group không inbound
- [ ] Tự tắt đã thử; mở được ComfyUI qua Session Manager
