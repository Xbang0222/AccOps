import React, { useState, useEffect, useRef } from 'react';
import { Typography, Progress, message, Tooltip, Flex, theme as antTheme } from 'antd';
import { generateTOTP } from '@/utils/totp';

const { Text } = Typography;

interface TOTPDisplayProps {
  secret: string;
}

const TOTPDisplay: React.FC<TOTPDisplayProps> = ({ secret }) => {
  const { token } = antTheme.useToken();
  const [totp, setTotp] = useState({ code: '------', remaining: 30, formatted: '--- ---' });
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const update = () => setTotp(generateTOTP(secret));
    update();
    intervalRef.current = setInterval(update, 1000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [secret]);

  const copyCode = () => {
    navigator.clipboard.writeText(totp.code).then(() => {
      message.success('验证码已复制');
    });
  };

  const percent = (totp.remaining / 30) * 100;
  const isUrgent = totp.remaining <= 10;
  const color = isUrgent ? '#ff4d4f' : '#4285f4';

  return (
    <Tooltip title="点击复制验证码">
      <Flex
        align="center"
        gap={6}
        onClick={copyCode}
        style={{ cursor: 'pointer', userSelect: 'none' }}
      >
        <Progress
          type="circle"
          percent={percent}
          size={22}
          strokeColor={color}
          trailColor={token.colorBorderSecondary}
          format={() => ''}
          strokeWidth={4}
        />
        <Text
          strong
          style={{
            fontFamily: "'SF Mono', Consolas, monospace",
            fontSize: 14,
            color,
            transition: 'color 0.3s',
          }}
        >
          {totp.formatted}
        </Text>
      </Flex>
    </Tooltip>
  );
};

export default TOTPDisplay;
