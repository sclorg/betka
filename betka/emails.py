from logging import getLogger
from smtplib import SMTP
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate
from email.mime.text import MIMEText

from betka.utils import text_from_template

logger = getLogger(__name__)


class BetkaEmails(object):
    @staticmethod
    def build_email_message(template_dir, template_filename, template_data):
        """Redirect"""
        return text_from_template(template_dir, template_filename, template_data)

    @staticmethod
    def send_email(text, receivers, subject, sender="phracek@redhat.com", smtp_server="smtp.redhat.com"):
        """
        Send an email from SENDER_EMAIL to all provided receivers
        :param text: string, body of email
        :param receivers: list, email receivers
        :param subject: string, email subject
        :param sender: string, sender email
        :param smtp_server: string, smtp server hostname
        """
        logger.info("Sending email to: %s", str(receivers))

        msg = MIMEMultipart()
        msg["From"] = sender
        msg["To"] = ", ".join(receivers)
        msg["Date"] = formatdate(localtime=True)
        msg["Subject"] = subject
        msg.attach(MIMEText(text))

        smtp = SMTP(smtp_server)
        smtp.sendmail(sender, receivers, msg.as_string())
        smtp.close()
        logger.debug("Email sent")
