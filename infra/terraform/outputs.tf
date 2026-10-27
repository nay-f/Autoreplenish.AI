output "table_name" {
  value = aws_dynamodb_table.core.name
}

output "approval_queue_url" {
  value = aws_sqs_queue.approval.url
}

output "approval_dlq_url" {
  value = aws_sqs_queue.approval_dlq.url
}

output "scheduler_dlq_url" {
  value = aws_sqs_queue.scheduler_dlq.url
}

output "orchestrator_schedule_names" {
  value = concat(aws_scheduler_schedule.morning[*].name, aws_scheduler_schedule.afternoon[*].name)
}
